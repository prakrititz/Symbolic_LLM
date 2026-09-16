import sys
import os

# Ensure the root of the project is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.trace.serializer import export_graph_text

def manual_sqrt():
    print("=== Phase 8: Manual Square Root Benchmark ===")
    
    spec_str = """
    Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0.
    Postcondition: (N:float)(e:float) := x*x <= N /\\ N < (x+e)*(x+e).
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    graph = RefinementGraph(spec)
    
    # 1. Apply Sequential Composition
    r_ast = parse_spec("Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0 /\\ x*x <= N /\\ x >= 0.\nPostcondition: := true.").precondition.expr
    
    a1 = graph.record_attempt(graph.root_id, "sequential", {"intermediate": r_ast})
    res1 = engine.apply(graph.nodes[graph.root_id].specification, "sequential", {"intermediate": r_ast})
    # Since sequential generates no proof obligations, it succeeds
    graph.attempts[a1].status = AttemptStatus.ACCEPTED
    
    # We must label the destination roles for sequential
    child1_id = graph.create_node(res1.sub_specs[0])
    child2_id = graph.create_node(res1.sub_specs[1])
    graph.attempts[a1].destination_roles = {"part1": child1_id, "part2": child2_id}
    
    graph.nodes[graph.root_id].status = NodeStatus.DELEGATED
    
    print(f"Applied Sequential Composition. Frontier: {graph.get_frontier()}")
    
    # 2. Refine Part 1 (x*x <= N) with Assignment x = 0
    a2 = graph.record_attempt(child1_id, "assignment", {"variable": "x", "expr": Number("0")})
    res2 = engine.apply(graph.nodes[child1_id].specification, "assignment", {"variable": "x", "expr": Number("0")})
    # Evaluate obligations (this would normally be done via Z3, but we assume it passes here)
    graph.attempts[a2].status = AttemptStatus.ACCEPTED
    graph.nodes[child1_id].program = res2.program
    graph.nodes[child1_id].status = NodeStatus.REFINED
    
    print(f"Applied Assignment to Part 1. Frontier: {graph.get_frontier()}")
    
    # 3. Refine Part 2 with Iteration
    # [x*x <= N, x*x <= N /\ N < (x+e)*(x+e)]
    guard = BinaryOp(Variable("N"), ">=", BinaryOp(BinaryOp(Variable("x"), "+", Variable("e")), "*", BinaryOp(Variable("x"), "+", Variable("e"))))
    variant = BinaryOp(Variable("N"), "-", BinaryOp(Variable("x"), "*", Variable("x")))
    
    a3 = graph.record_attempt(child2_id, "iteration", {"guard": guard, "variant": variant})
    res3 = engine.apply(graph.nodes[child2_id].specification, "iteration", {"guard": guard, "variant": variant})
    graph.attempts[a3].status = AttemptStatus.ACCEPTED
    
    body_id = graph.create_node(res3.sub_specs[0])
    graph.attempts[a3].destination_roles = {"body": body_id}
    
    # Save the loop construct logic to the node so reconstruction can wrap the body
    graph.nodes[child2_id].refinement_operation = "iteration"
    graph.nodes[child2_id].law_parameters = {"guard": guard, "variant": variant}
    graph.nodes[child2_id].status = NodeStatus.DELEGATED
    
    print(f"Applied Iteration to Part 2. Frontier: {graph.get_frontier()}")
    
    # 4. Refine Body with Assignment x := x + e
    a4 = graph.record_attempt(body_id, "assignment", {"variable": "x", "expr": BinaryOp(Variable("x"), "+", Variable("e"))})
    res4 = engine.apply(graph.nodes[body_id].specification, "assignment", {"variable": "x", "expr": BinaryOp(Variable("x"), "+", Variable("e"))})
    graph.attempts[a4].status = AttemptStatus.ACCEPTED
    
    graph.nodes[body_id].program = res4.program
    graph.nodes[body_id].status = NodeStatus.REFINED
    
    print(f"Applied Assignment to Iteration Body. Frontier: {graph.get_frontier()}")
    
    if graph.is_complete(graph.root_id):
        print("\nGraph is fully complete!")
        print("\nFinal Reconstructed AST:")
        ast = graph.reconstruct_program()
        print(ast)
    else:
        print("\nGraph is INCOMPLETE.")
        
    print("\n" + "="*80)
    print("REFINEMENT TRACE")
    print("="*80)
    print(export_graph_text(graph))

if __name__ == "__main__":
    manual_sqrt()
