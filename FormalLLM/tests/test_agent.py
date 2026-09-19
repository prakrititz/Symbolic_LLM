import json
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.llm.provider import MockProvider
from FormalLLM.agent.refiner import AutomatedRefiner
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus

def test_refiner_success():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    # LLM returns an assignment law directly
    responses = [
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "0"
            }
        })
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm)
    
    graph = RefinementGraph(spec)
    result = refiner.refine_node(graph, graph.root_id)
    
    assert result is True
    root = graph.nodes[graph.root_id]
    
    # Check that root was terminally refined
    assert root.status == NodeStatus.REFINED
    assert root.program is not None
    assert root.program.variable == "x"

def test_refiner_feedback_loop():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    # Attempt 1: bad assignment (x = 100). Fails because 100*100 <= N is not true for all N >= 0.
    # Attempt 2: good assignment (x = 0).
    responses = [
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "100"
            }
        }),
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "0"
            }
        })
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm)
    
    graph = RefinementGraph(spec)
    result = refiner.refine_node(graph, graph.root_id)
    
    assert result is True
    assert mock_llm.call_count == 2
    # Check that feedback was in the second prompt
    assert "Previous failed attempts:" in mock_llm.prompts_received[1]
    assert "Counterexample" in mock_llm.prompts_received[1]


def test_refiner_state_leak_and_blacklist_scoping():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    # We will simulate a multi-turn process where:
    # 1. Turn 1 picks 'assignment'
    # 2. Turn 2 (synthesis) picks x = 100 -> FAILS
    # 3. Turn 2 (synthesis) picks x = 50 -> FAILS (exhausts max_param_attempts)
    # 4. Turn 1 picks 'skip'
    # 5. Turn 2 (synthesis) picks nothing -> FAILS
    responses = [
        # Attempt 1: Law selection
        json.dumps({"law": "assignment"}),
        # Attempt 1, Eval 1: Parameters
        json.dumps({"parameters": {"variable": "x", "expr": "100"}, "rationale": "try 1"}),
        # Attempt 1, Eval 2: Parameters (Retry for assignment)
        json.dumps({"parameters": {"variable": "x", "expr": "50"}, "rationale": "try 2"}),
        
        # Attempt 2: Law selection (assignment is now blacklisted)
        json.dumps({"law": "skip"}),
        # Attempt 2, Eval 1: Parameters for skip
        json.dumps({"parameters": {}, "rationale": "just skip"})
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, use_multi_turn=True)
    refiner.max_param_attempts = 2  # exactly 2 tries
    
    graph = RefinementGraph(spec)
    import pytest
    from FormalLLM.agent.refiner import RefinementExhausted
    with pytest.raises(RefinementExhausted):
        refiner.refine_node(graph, graph.root_id)
    
    # Check the prompts
    # 0: Law selection for assignment
    # 1: Parameter synthesis for assignment (fresh)
    # 2: Parameter synthesis for assignment (retry)
    # 3: Law selection for skip (assignment blacklisted)
    # 4: Parameter synthesis for skip (fresh)
    
    assert "[fresh attempt" in mock_llm.prompts_received[1]
    
    assert "[retry" in mock_llm.prompts_received[2]
    assert "100" in mock_llm.prompts_received[2]  # Feedback from attempt 1
    
    # Verify blacklist scoping in law selection prompt
    law_selection_skip = mock_llm.prompts_received[3]
    assert "assignment" in law_selection_skip
    assert "Blacklisted laws: ['assignment']" in law_selection_skip or "exhausted" in law_selection_skip.lower()
    
    # Verify state leak prevention: parameter synthesis for 'skip' should NOT have 'assignment' feedback
    param_synthesis_skip = mock_llm.prompts_received[4]
    assert "[fresh attempt" in param_synthesis_skip
    assert "50" not in param_synthesis_skip
    assert "Counterexample" not in param_synthesis_skip
