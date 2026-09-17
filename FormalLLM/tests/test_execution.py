import pytest
from FormalLLM.lspec.ast import *
from FormalLLM.lpl.ast import *
from FormalLLM.lpl.to_python import expr_to_python, to_python
from FormalLLM.execution.testcase import TestCase
from FormalLLM.execution.runner import run

def test_expr_to_python():
    # Test binary ops
    assert expr_to_python(BinaryOp(Variable("x"), "+", Number("1"))) == "(x + 1)"
    assert expr_to_python(BinaryOp(Variable("x"), "/\\", Variable("y"))) == "(x and y)"
    assert expr_to_python(BinaryOp(Variable("a"), "\\/", Variable("b"))) == "(a or b)"
    assert expr_to_python(BinaryOp(Variable("x"), "=", Number("5"))) == "(x == 5)"
    assert expr_to_python(BinaryOp(Variable("y"), "<>", Number("0"))) == "(y != 0)"
    
    # Test unary ops
    assert expr_to_python(UnaryOp("~", Variable("cond"))) == "(not cond)"
    assert expr_to_python(UnaryOp("-", Variable("x"))) == "(-x)"
    
    # Test quantifiers raise error
    with pytest.raises(NotImplementedError):
        expr_to_python(QuantifiedExpr("forall", [Param("i", IntType())], Variable("i")))

def test_to_python_ast():
    # Assignment
    node = Assignment("x", BinaryOp(Variable("x"), "+", Number("1")))
    assert to_python(node) == "x = (x + 1)"
    
    # Sequential
    seq = SequentialComposition(
        Assignment("x", Number("1")),
        Assignment("y", Number("2"))
    )
    assert to_python(seq) == "x = 1\ny = 2"
    
    # IfElse
    ifelse = IfElse(
        BinaryOp(Variable("x"), ">", Number("0")),
        Assignment("y", Number("1")),
        Skip()
    )
    assert to_python(ifelse) == "if (x > 0):\n    y = 1\nelse:\n    pass"

    # While
    whl = While(
        BinaryOp(Variable("x"), "<", Number("10")),
        Assignment("x", BinaryOp(Variable("x"), "+", Number("1")))
    )
    assert to_python(whl) == "while (x < 10):\n    x = (x + 1)"

def test_runner_exact_expected():
    program = "x = N + 1"
    tests = [
        TestCase(inputs={"N": 5}, expected={"x": 6}),
        TestCase(inputs={"N": 0}, expected={"x": 1})
    ]
    res = run(program, tests, output_vars=["x"])
    assert res.passed == 2
    assert res.failed == 0

def test_runner_postcondition():
    program = "x = 0"
    tests = [
        TestCase(inputs={"N": 16.0}, expected=None),
        TestCase(inputs={"N": 0.0}, expected=None)
    ]
    # Postcondition for C1: x*x <= N
    res = run(program, tests, output_vars=["x"], postcondition_expr="(x * x) <= N")
    assert res.passed == 2
    assert res.failed == 0

def test_runner_timeout():
    program = "while True: pass"
    tests = [TestCase(inputs={}, expected={})]
    res = run(program, tests, output_vars=[])
    assert res.timeout == True
    assert res.failed == 1
