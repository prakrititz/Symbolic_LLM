import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.frame import obligation_params
from FormalLLM.verification.z3_backend import verify_obligation
from FormalLLM.verification.proof_obligations import ProofObligation

def test_obligation_params_includes_frame_types():
    """
    Frame variables must be included in obligation_params with their correct types
    so Z3 doesn't default them to Real. This prevents integer quotient bugs (like -9/8).
    """
    spec = parse_spec("Frame: q:int, r:int.\nPrecondition: (n:int) := n >= 0.\nPostcondition: (n:int) := true.")
    params = obligation_params(spec)
    
    names = [p.name for p in params]
    assert "q" in names
    assert "r" in names
    
    q_param = next(p for p in params if p.name == "q")
    assert type(q_param.type_).__name__ == "IntType", "Frame variable 'q' lost its integer type"
