import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.lspec.z3_translator import Z3Translator

def test_parse_sqrt_example():
    spec_str = """
    Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0.
    Postcondition: (N:float)(e:float) := x*x <= N /\\ N < y*y /\\ y <= x+e.
    """
    # Note: paper used `x*x <= N < y*y`, we split it into `x*x <= N /\ N < y*y` because
    # `<Logit>` grammar doesn't explicitly support chained inequalities natively without 
    # expanding them (e.g. term < logit < logit isn't in Table 1).
    ast = parse_spec(spec_str)
    
    assert isinstance(ast, Spec)
    assert len(ast.precondition.params) == 2
    assert ast.precondition.params[0].name == 'N'
    assert isinstance(ast.precondition.params[0].type_, FloatType)
    
    # Check that N is a Variable inside the precondition expr, not Const
    assert isinstance(ast.precondition.expr.left, BinaryOp) # N >= 0
    assert isinstance(ast.precondition.expr.left.left, Variable)
    assert ast.precondition.expr.left.left.name == 'N'
    
    # Verify Z3 translation works without errors
    translator = Z3Translator()
    z3_expr = translator.translate(ast)
    assert z3_expr is not None

def test_parse_quantified():
    spec_str = """
    Precondition: := forall (x:int)(y:int) x + y = y + x.
    Postcondition: := true.
    """
    ast = parse_spec(spec_str)
    assert isinstance(ast.precondition.expr, QuantifiedExpr)
    assert ast.precondition.expr.quantifier == 'forall'
    
    translator = Z3Translator()
    z3_expr = translator.translate(ast)
    assert z3_expr is not None
