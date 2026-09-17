import json
import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.llm.provider import MockProvider
from FormalLLM.agent.refiner import AutomatedRefiner, RefinementExhausted
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus

# NOTE: the intermediate below is "N > -1" rather than "N >= 0". With "N >= 0"
# the second sub-spec [N >= 0, x*x <= N] is *identical to the parent*, which the
# refiner's progress guard now rejects as a no-op. "N > -1" is implied by the
# precondition (so the scripted skip still succeeds) while genuinely changing the
# specification, preserving what these tests are actually exercising: fallback
# when a child cannot be refined.

def test_fallback_mechanism():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    responses = [
        json.dumps({"law": "sequential", "parameters": {"intermediate": "N > -1"}}),
        json.dumps({"law": "skip", "parameters": {}}),
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "100"}}),
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "200"}}),
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "0"}}),
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    graph = RefinementGraph(spec)
    result = refiner.refine_node(graph, graph.root_id)
    
    assert result is True
    root = graph.nodes[graph.root_id]
    
    # We should have a successful ACCEPTED attempt for assignment on the root
    accepted_attempts = [graph.attempts[a_id] for a_id in root.attempts if graph.attempts[a_id].status == AttemptStatus.ACCEPTED]
    assert len(accepted_attempts) == 1
    assert accepted_attempts[0].law == "assignment"
    
    # The failed `sequential` step is recorded against its *parameters*, not
    # blacklisted outright. A law whose sub-specification could not be refined
    # is usually the right law with the wrong parameters -- an invariant too
    # weak to discharge the loop body, say -- and banning it after one attempt
    # forces the model to abandon an approach it should be repairing. It is
    # only blacklisted once `max_param_attempts` different parameter choices
    # have failed.
    assert refiner.param_failures_per_node[(graph.root_id, "sequential")] == 1
    assert "sequential" not in refiner.blacklisted_laws_per_node[graph.root_id]


def test_fallback_discards_succeeded_sibling():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    responses = [
        json.dumps({"law": "sequential", "parameters": {"intermediate": "N > -1"}}),
        json.dumps({"law": "skip", "parameters": {}}), # Child 1 succeeds
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "100"}}), # Child 2 fails attempt 0
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "200"}}), # Child 2 fails attempt 1 -> exhausts retries
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "0"}}), # Root retries and succeeds
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    graph = RefinementGraph(spec)
    result = refiner.refine_node(graph, graph.root_id)
    
    assert result is True
    root = graph.nodes[graph.root_id]
    
    accepted_attempts = [graph.attempts[a_id] for a_id in root.attempts if graph.attempts[a_id].status == AttemptStatus.ACCEPTED]
    assert len(accepted_attempts) == 1
    assert accepted_attempts[0].law == "assignment"


def test_fallback_root_failure():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    responses = [
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "100"}})
    ] * 5
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    graph = RefinementGraph(spec)
    
    with pytest.raises(RefinementExhausted):
        refiner.refine_node(graph, graph.root_id)


def test_law_may_be_retried_with_different_parameters():
    """A deep failure must not ban the law -- only that parameter choice.

    The model's first `iteration` invariant is too weak to discharge the loop
    body. The old refiner blacklisted `iteration` at that point, so the correct
    law became unavailable and the search had to wander elsewhere. It should
    instead be re-proposable with a stronger invariant.
    """
    spec = parse_spec(
        "Frame: x.\n"
        "Precondition: (N:float)(e:float) := N >= 0 /\ e > 0.\n"
        "Postcondition: (N:float)(e:float) := x*x <= N /\ N < (x+e)*(x+e)."
    )

    weak = json.dumps({"law": "iteration", "parameters": {
        "invariant": "(x * x) <= N",                 # too weak: admits x < 0
        "guard": "N >= (x + e) * (x + e)", "variant": "N - (x * x)"}})
    strong = json.dumps({"law": "iteration", "parameters": {
        "invariant": "(x * x) <= N && x >= 0",       # repaired
        "guard": "N >= (x + e) * (x + e)", "variant": "N - (x * x)"}})
    assign_zero = json.dumps({"law": "assignment",
                              "parameters": {"variable": "x", "expr": "0"}})
    assign_step = json.dumps({"law": "assignment",
                              "parameters": {"variable": "x", "expr": "x + e"}})

    # With max_retries=2 the sequence is: root proposes the weak invariant;
    # init succeeds; the body burns both its retries; the root is re-prompted
    # and proposes the strong invariant; init and body then succeed.
    responses = [weak, assign_zero, assign_step, assign_step,
                 strong, assign_zero, assign_step]
    refiner = AutomatedRefiner(RefinementEngine(), MockProvider(responses),
                               max_retries=2)
    graph = RefinementGraph(spec)

    assert refiner.refine_node(graph, graph.root_id) is True
    assert "iteration" not in refiner.blacklisted_laws_per_node[graph.root_id]

    laws = [graph.attempts[a].law for a in graph.nodes[graph.root_id].attempts]
    assert laws.count("iteration") == 2, "iteration should be re-proposed, not banned"


def test_subtree_failure_reason_reaches_the_parent():
    """The parent's retry prompt must carry the counterexample from below."""
    spec = parse_spec(
        "Frame: x.\n"
        "Precondition: (N:float)(e:float) := N >= 0 /\ e > 0.\n"
        "Postcondition: (N:float)(e:float) := x*x <= N /\ N < (x+e)*(x+e)."
    )
    weak = json.dumps({"law": "iteration", "parameters": {
        "invariant": "(x * x) <= N",
        "guard": "N >= (x + e) * (x + e)", "variant": "N - (x * x)"}})
    assign_step = json.dumps({"law": "assignment",
                              "parameters": {"variable": "x", "expr": "x + e"}})

    assign_zero = json.dumps({"law": "assignment",
                              "parameters": {"variable": "x", "expr": "0"}})
    llm = MockProvider([weak, assign_zero, assign_step, assign_step])
    refiner = AutomatedRefiner(RefinementEngine(), llm, max_retries=2)
    graph = RefinementGraph(spec)
    # The scripted replies never repair the invariant, so the root legitimately
    # gives up; what matters here is what it was told on the way.
    with pytest.raises(RefinementExhausted):
        refiner.refine_node(graph, graph.root_id)

    # After the body fails, the next prompt sent for the root must explain why.
    later = "\n".join(llm.prompts_received[1:])
    assert "must show" in later or "Counterexample" in later, (
        "the parent was not told what failed below it"
    )
