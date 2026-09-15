import json
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.llm.provider import MockProvider
from FormalLLM.agent.refiner import AutomatedRefiner
from FormalLLM.refinement.tree import RefinementNode

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
    
    root = RefinementNode(specification=spec)
    result = refiner.refine_node(root)
    
    assert result is True
    assert root.refinement_operation == "assignment"
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
    
    root = RefinementNode(specification=spec)
    result = refiner.refine_node(root)
    
    assert result is True
    assert mock_llm.call_count == 2
    # Check that feedback was in the second prompt
    assert "Feedback from previous attempt" in mock_llm.prompts_received[1]
    assert "Verification failed" in mock_llm.prompts_received[1]
