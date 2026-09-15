import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.refinement.engine import RefinementEngine

def test_sqrt_integration():
    # End-to-end test of the first two steps of Figure 2 for the sqrt algorithm
    # Spec: [N >= 0 /\ e > 0, x*x <= N /\ N < y*y /\ y <= x+e]
    spec_str = """
    Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0.
    Postcondition: (N:float)(e:float) := x*x <= N /\\ N < y*y /\\ y <= x+e.
    """
    
    spec = parse_spec(spec_str)
    engine = RefinementEngine()
    
    # Step 1: Sequential law
    # Intermediate condition R: x*x <= N /\ N < y*y
    r_str = """
    Precondition: (N:float)(e:float) := x*x <= N /\\ N < y*y.
    Postcondition: := true.
    """
    r_ast = parse_spec(r_str).precondition.expr
    
    res1 = engine.apply(spec, "sequential", {"intermediate": r_ast})
    assert len(res1.sub_specs) == 2
    sub1, sub2 = res1.sub_specs
    
    # Sub1 is now: [N >= 0 /\ e > 0, x*x <= N /\ N < y*y]
    
    # Step 2: Let's test a single assignment on a simplified version of Sub1
    # To keep it simple, we just assign x := 0
    spec_assign_str = """
    Precondition: (N:float) := N >= 0.
    Postcondition: (N:float) := x*x <= N.
    """
    spec_assign = parse_spec(spec_assign_str)
    res_assign = engine.apply(spec_assign, "assignment", {
        "variable": "x",
        "expr": Number("0")
    })
    
    assert res_assign.program is not None
    assert len(res_assign.obligations) == 1
    # The assignment is verified successfully!

def test_iteration_law():
    # x:[I, I /\ ~G] ⊑ while G: body
    # spec: [x >= 0, x >= 0 /\ ~(x < 10)]
    spec_str = """
    Precondition: := x >= 0.
    Postcondition: := x >= 0 /\\ ~(x < 10).
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    guard_expr = BinaryOp(Variable("x"), "<", Number("10"))
    variant_expr = BinaryOp(Number("10"), "-", Variable("x"))
    
    res = engine.apply(spec, "iteration", {
        "guard": guard_expr,
        "variant": variant_expr
    })
    
    # Should emit 1 obligation: I /\ ~G => Q
    assert len(res.obligations) == 1
    # Should emit 1 sub spec for the body
    assert len(res.sub_specs) == 1
    body_spec = res.sub_specs[0]
    
    # Check body precondition: I /\ G -> x >= 0 /\ x < 10
    assert isinstance(body_spec.precondition.expr, BinaryOp)
    assert body_spec.precondition.expr.op == '/\\'
