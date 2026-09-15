import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import *
from FormalLLM.refinement.engine import RefinementEngine, VerificationError

def test_valid_assignment():
    # [x >= 0, y = x + 1]
    # y := x + 1
    spec_str = """
    Precondition: := x >= 0.
    Postcondition: := y = x + 1.
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    result = engine.apply(spec, "assignment", {
        "variable": "y",
        "expr": BinaryOp(Variable("x"), "+", Number("1"))
    })
    
    assert result.program is not None
    assert result.program.variable == "y"
    
def test_invalid_assignment():
    # [x >= 0, y = x + 1]
    # y := x + 2
    spec_str = """
    Precondition: := x >= 0.
    Postcondition: := y = x + 1.
    """
    spec = parse_spec(spec_str)
    
    engine = RefinementEngine()
    
    with pytest.raises(VerificationError) as excinfo:
        engine.apply(spec, "assignment", {
            "variable": "y",
            "expr": BinaryOp(Variable("x"), "+", Number("2"))
        })
        
    assert "Refinement invalid" in str(excinfo.value)
    assert "Counterexample found" in str(excinfo.value)
