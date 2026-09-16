import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.lpl.ast import *
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.llm.prompts import to_string

def test_mixed_program_reconstruction():
    spec_str = """
    Precondition: (x:int) := x >= 0.
    Postcondition: (x:int) := x = 0.
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    graph = RefinementGraph(spec)
    
    # Initial state should be a Spec
    mixed0 = graph.reconstruct_mixed_program()
    assert isinstance(mixed0, Spec)
    
    # 1. Apply Alternation
    guard = BinaryOp(Variable("x"), ">", Number("0"))
    res1 = engine.apply(graph.nodes[graph.root_id].specification, "alternation", {"guard": guard})
    a1 = graph.record_attempt(graph.root_id, "alternation", {"guard": guard})
    
    # Transition to ACCEPTED and setup roles
    graph.attempts[a1].status = AttemptStatus.ACCEPTED
    then_id = graph.create_node(res1.sub_specs[0])
    else_id = graph.create_node(res1.sub_specs[1])
    graph.attempts[a1].destination_roles = {"then": then_id, "else": else_id}
    graph.nodes[graph.root_id].status = NodeStatus.DELEGATED
    
    mixed1 = graph.reconstruct_mixed_program()
    assert isinstance(mixed1, IfElse)
    # Validate guard is extracted from attempt.parameters
    assert isinstance(mixed1.guard, BinaryOp)
    assert mixed1.guard.op == ">"
    assert isinstance(mixed1.then_branch, Spec)
    assert isinstance(mixed1.else_branch, Spec)
    
    # 2. Stringify Mixed AST
    rendered = to_string(mixed1)
    
    # It should use compact notation for the nested specs
    assert "if (x > 0):" in rendered
    assert "[((x >= 0) /\\ (x > 0)), (x = 0)]" in rendered  # then branch
    assert "[((x >= 0) /\\ (~(x > 0))), (x = 0)]" in rendered # else branch

def test_mixed_program_sequential_assignment():
    spec_str = """
    Precondition: (x:int) := true.
    Postcondition: (x:int) := x = 0.
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    graph = RefinementGraph(spec)
    
    r_ast = parse_spec("Precondition: (x:int) := x = 0.\nPostcondition: := true.").precondition.expr
    
    res1 = engine.apply(graph.nodes[graph.root_id].specification, "sequential", {"intermediate": r_ast})
    a1 = graph.record_attempt(graph.root_id, "sequential", {"intermediate": r_ast})
    
    graph.attempts[a1].status = AttemptStatus.ACCEPTED
    part1_id = graph.create_node(res1.sub_specs[0])
    part2_id = graph.create_node(res1.sub_specs[1])
    graph.attempts[a1].destination_roles = {"part1": part1_id, "part2": part2_id}
    graph.nodes[graph.root_id].status = NodeStatus.DELEGATED
    
    res2 = engine.apply(graph.nodes[part1_id].specification, "assignment", {"variable": "x", "expr": Number("0")})
    a2 = graph.record_attempt(part1_id, "assignment", {"variable": "x", "expr": Number("0")})
    graph.attempts[a2].status = AttemptStatus.ACCEPTED
    graph.nodes[part1_id].program = res2.program
    graph.nodes[part1_id].status = NodeStatus.REFINED
    
    mixed = graph.reconstruct_mixed_program()
    assert isinstance(mixed, SequentialComposition)
    assert isinstance(mixed.first, Assignment)
    assert isinstance(mixed.second, Spec)
    
    rendered = to_string(mixed)
    assert "x := 0 ;\n" in rendered
    assert "[((x == 0) /\\ (x >= 0)), (x == 0)]" not in rendered # wait, part2 has preconditions from Sequential
    
    # Print rendered for debug
    print(rendered)
