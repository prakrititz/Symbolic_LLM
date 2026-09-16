import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.refinement.engine import RefinementEngine, VerificationError
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus

def test_deliberate_failure_and_recovery():
    # We use a simple spec: [N >= 0, x*x <= N]
    spec_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    graph = RefinementGraph(spec)
    
    root_id = graph.root_id
    
    # 1. Deliberately feed a wrong candidate: x := 100
    a1_id = graph.record_attempt(root_id, "assignment", {"variable": "x", "expr": Number("100")})
    
    with pytest.raises(VerificationError) as exc_info:
        engine.apply(graph.nodes[root_id].specification, "assignment", {"variable": "x", "expr": Number("100")})
        
    assert "Counterexample" in str(exc_info.value)
    
    # Mark the attempt as REJECTED
    graph.attempts[a1_id].status = AttemptStatus.REJECTED
    graph.attempts[a1_id].status_history.append((AttemptStatus.REJECTED, str(exc_info.value)))
    
    assert graph.nodes[root_id].status == NodeStatus.REFINING
    assert graph.attempts[a1_id].status == AttemptStatus.REJECTED
    
    # 2. Feed a correct candidate: x := 0
    a2_id = graph.record_attempt(root_id, "assignment", {"variable": "x", "expr": Number("0")})
    
    res = engine.apply(graph.nodes[root_id].specification, "assignment", {"variable": "x", "expr": Number("0")})
    
    # Since it did not raise VerificationError, it is successfully PROVED.
    graph.attempts[a2_id].status = AttemptStatus.ACCEPTED
    graph.attempts[a2_id].status_history.append((AttemptStatus.ACCEPTED, "PROVED"))
    
    graph.nodes[root_id].program = res.program
    graph.nodes[root_id].status = NodeStatus.REFINED
    
    assert graph.attempts[a2_id].status == AttemptStatus.ACCEPTED
    assert graph.nodes[root_id].status == NodeStatus.REFINED
    assert graph.is_complete(root_id)
    assert graph.reconstruct_program().variable == "x"
