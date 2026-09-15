import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.graph.graph import RefinementGraph, IncompleteRefinementError
from FormalLLM.refinement.graph.status import AttemptStatus, NodeStatus

def get_dummy_spec():
    return parse_spec("Precondition: (N:float) := N >= 0.\nPostcondition: (N:float) := true.")

def test_liveness_and_frontier_exclusion():
    spec = get_dummy_spec()
    graph = RefinementGraph(spec)
    root = graph.nodes[graph.root_id]
    
    # Root creates A0 (sequential)
    a0_id = graph.record_attempt(root.id, "sequential", {})
    a0 = graph.attempts[a0_id]
    
    # A0 succeeds and creates N1 and N2
    n1_id = graph.create_node(spec)
    n2_id = graph.create_node(spec)
    
    a0.destination_roles = {"part1": n1_id, "part2": n2_id}
    a0.update_status(AttemptStatus.ACCEPTED)
    root.status = NodeStatus.DELEGATED
    
    # Both N1 and N2 should be in the frontier
    frontier_ids = [n.id for n in graph.get_frontier()]
    assert n1_id in frontier_ids
    assert n2_id in frontier_ids
    
    # Now suppose N1 refines successfully
    a1_id = graph.record_attempt(n1_id, "skip", {})
    a1 = graph.attempts[a1_id]
    a1.update_status(AttemptStatus.ACCEPTED)
    graph.nodes[n1_id].status = NodeStatus.REFINED
    
    # N1 is no longer OPEN, so it leaves frontier
    frontier_ids = [n.id for n in graph.get_frontier()]
    assert n1_id not in frontier_ids
    assert n2_id in frontier_ids
    
    # Now suppose N2 FAILS entirely. The parent A0 is ABORTED.
    a0.update_status(AttemptStatus.ABORTED)
    root.status = NodeStatus.OPEN
    
    # What happens to the frontier? N2 is OPEN, but A0 is no longer ACCEPTED.
    # So N2 is no longer live.
    assert not graph.is_live(n2_id)
    assert not graph.is_live(n1_id)
    assert graph.is_live(root.id)
    
    frontier_ids = [n.id for n in graph.get_frontier()]
    assert n2_id not in frontier_ids
    # Root is OPEN and live, so it enters the frontier again!
    assert root.id in frontier_ids

def test_no_premature_completion():
    spec = get_dummy_spec()
    graph = RefinementGraph(spec)
    root = graph.nodes[graph.root_id]
    
    # Root creates A0 (sequential)
    a0_id = graph.record_attempt(root.id, "sequential", {})
    a0 = graph.attempts[a0_id]
    
    # A0 succeeds and creates N1 and N2
    n1_id = graph.create_node(spec)
    n2_id = graph.create_node(spec)
    
    a0.destination_roles = {"part1": n1_id, "part2": n2_id}
    a0.update_status(AttemptStatus.ACCEPTED)
    root.status = NodeStatus.DELEGATED
    
    # The parent node is DELEGATED, but children are OPEN.
    # Therefore, the parent is NOT complete.
    assert not graph.is_complete(root.id)
    
    with pytest.raises(IncompleteRefinementError):
        graph.reconstruct_program()
