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
    
    # Check that sequential is in the blacklist for the root node
    assert "sequential" in refiner.blacklisted_laws_per_node[graph.root_id]


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
