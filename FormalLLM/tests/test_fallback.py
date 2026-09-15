import json
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.llm.provider import MockProvider
from FormalLLM.agent.refiner import AutomatedRefiner
from FormalLLM.refinement.tree import RefinementNode

def test_fallback_mechanism():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    # We want to test that a node abandons a law and falls back.
    # We'll use a sequential law.
    # The sequential law generates 2 children.
    # We will make child 1 succeed, but child 2 completely fail up to max_retries.
    # This should trigger a fallback at the parent, causing it to blacklist "sequential" and try another law.
    # The parent will then try "assignment" and succeed.
    
    # Responses:
    # 1. Parent chooses sequential
    # 2. Child 1 (P->R) chooses skip (it succeeds trivially since we'll make P=R)
    # 3. Child 2 (R->Q) chooses assignment but fails repeatedly (max_retries = 2).
    # 4. Parent triggers fallback. "sequential" is blacklisted. Parent gets prompted again.
    # 5. Parent chooses assignment directly and succeeds.
    
    responses = [
        # 1. Parent -> sequential
        json.dumps({
            "law": "sequential",
            "parameters": {
                "intermediate": "N >= 0" # R = P, so P->R is trivial
            }
        }),
        # 2. Child 1 -> skip (P->R is N>=0 -> N>=0)
        json.dumps({
            "law": "skip",
            "parameters": {}
        }),
        # 3. Child 2 -> assignment fail 1 (R->Q)
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "100"
            }
        }),
        # 3. Child 2 -> assignment fail 2 (R->Q)
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "200"
            }
        }),
        # 4. Parent fallbacks and is prompted again, sequential is blacklisted.
        # Parent -> assignment success
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "0"
            }
        }),
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    root = RefinementNode(specification=spec)
    result = refiner.refine_node(root)
    
    assert result is True
    # The final law at the root should be assignment, because sequential was abandoned
    assert root.refinement_operation == "assignment"
    assert len(root.children) == 0
    
    # Check that sequential is in the blacklist for the root node
    assert "sequential" in refiner.blacklisted_laws_per_node[id(root)]


from FormalLLM.agent.refiner import RefinementFailure
import pytest

def test_fallback_discards_succeeded_sibling():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    responses = [
        json.dumps({"law": "sequential", "parameters": {"intermediate": "N >= 0"}}),
        json.dumps({"law": "skip", "parameters": {}}), # Child 1 succeeds
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "100"}}), # Child 2 fails attempt 0
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "200"}}), # Child 2 fails attempt 1 -> exhausts retries
        json.dumps({"law": "assignment", "parameters": {"variable": "x", "expr": "0"}}), # Root retries and succeeds
    ]
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    root = RefinementNode(specification=spec)
    result = refiner.refine_node(root)
    
    assert result is True
    assert root.refinement_operation == "assignment"
    assert len(root.children) == 0

def test_fallback_root_failure():
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    # We will just repeatedly fail verification on an assignment until max_retries hits.
    responses = [
        json.dumps({
            "law": "assignment",
            "parameters": {
                "variable": "x",
                "expr": "100"
            }
        })
    ] * 5
    
    mock_llm = MockProvider(responses)
    engine = RefinementEngine()
    refiner = AutomatedRefiner(engine, mock_llm, max_retries=2)
    
    root = RefinementNode(specification=spec)
    
    with pytest.raises(RefinementFailure):
        refiner.refine_node(root)
