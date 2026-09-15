import pytest
from FormalLLM.lspec.ast import *
from FormalLLM.lspec.substitution import substitute, get_free_vars, alpha_rename

def test_simple_substitute():
    # y = x + 1
    # substitute y with x + 1
    expr = BinaryOp(Variable('y'), '=', BinaryOp(Variable('x'), '+', Number('1')))
    replacement = BinaryOp(Variable('x'), '+', Number('1'))
    
    sub = substitute(expr, 'y', replacement)
    
    assert isinstance(sub, BinaryOp)
    assert sub.op == '='
    assert isinstance(sub.left, BinaryOp)
    assert sub.left.op == '+'
    assert isinstance(sub.left.left, Variable)
    assert sub.left.left.name == 'x'

def test_chained_substitute():
    # y * y <= N
    # substitute y with x + 1
    expr = BinaryOp(BinaryOp(Variable('y'), '*', Variable('y')), '<=', Const('N'))
    replacement = BinaryOp(Variable('x'), '+', Number('1'))
    
    sub = substitute(expr, 'y', replacement)
    
    # (x+1)*(x+1) <= N
    assert isinstance(sub.left, BinaryOp)
    assert sub.left.op == '*'
    assert isinstance(sub.left.left, BinaryOp)
    assert sub.left.left.left.name == 'x'
    assert isinstance(sub.left.right, BinaryOp)
    assert sub.left.right.left.name == 'x'
    assert sub.right.name == 'N'

def test_shadowing_substitute():
    # forall (x:int) x > 0
    # substitute x with y
    expr = QuantifiedExpr('forall', [Param('x', IntType())], BinaryOp(Variable('x'), '>', Number('0')))
    replacement = Variable('y')
    
    sub = substitute(expr, 'x', replacement)
    
    # Should be unmodified because x is bound
    assert sub.params[0].name == 'x'
    assert sub.expr.left.name == 'x'

def test_capture_avoidance_substitute():
    # forall (y:int) y > x
    # substitute x with y
    expr = QuantifiedExpr('forall', [Param('y', IntType())], BinaryOp(Variable('y'), '>', Variable('x')))
    replacement = Variable('y')
    
    sub = substitute(expr, 'x', replacement)
    
    # Inner y should be alpha-renamed to avoid capture by the outer forall
    # e.g., forall (y_fresh:int) y_fresh > y
    assert sub.params[0].name == 'y_fresh'
    assert sub.expr.left.name == 'y_fresh'
    assert sub.expr.right.name == 'y'

def test_prev_state_substitute():
    # x = x0 + 1
    # substitute x with y
    expr = BinaryOp(Variable('x'), '=', BinaryOp(VariablePreviousState('x'), '+', Number('1')))
    replacement = Variable('y')
    
    sub = substitute(expr, 'x', replacement)
    
    # y = x0 + 1
    assert sub.left.name == 'y'
    assert isinstance(sub.right.left, VariablePreviousState)
    assert sub.right.left.name == 'x' # Untouched
