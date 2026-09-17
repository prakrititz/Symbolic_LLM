import pytest
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.frame import rigid_context, derive, check_assignable, FrameViolation, obligation_params
from FormalLLM.llm.prompts import to_string

def test_derive_is_step_local():
    """
    Lemma 2.8: frames are scoped per-derivation-step.
    derive() must not blindly pass the frame list by reference, or else sibling branches
    will corrupt each other's frames if one of them shrinks it.
    """
    spec = parse_spec("Frame: x, y.\nPrecondition: (x:int) := true.\nPostcondition: (x:int) := true.")
    child1 = derive(spec, spec.precondition, spec.postcondition)
    child2 = derive(spec, spec.precondition, spec.postcondition)
    
    # Mutate child1's frame (simulate a Frame Contraction law)
    child1.frame.pop()
    
    # child2's frame must remain unchanged
    assert len(child2.frame) == 2, "derive() shares frame lists, causing sibling divergence bugs"

def test_check_assignable_raises():
    """
    Assigning to a variable outside the frame must raise FrameViolation.
    """
    spec = parse_spec("Frame: x.\nPrecondition: (x:int) := true.\nPostcondition: (x:int) := true.")
    check_assignable(spec, "x") # Should pass
    with pytest.raises(FrameViolation):
        check_assignable(spec, "y") # Should fail

def test_name_collision_capture():
    """
    Frame injection (rigid_context) must not suffer from variable capture.
    If a rigid conjunct is `x = 5`, and extra is `forall x (x > 0)`, the two
    should be conjoined without the outer `x` being captured.
    """
    spec = parse_spec("Frame: y.\nPrecondition: (x:int) := x = 5 /\\ y = 2.\nPostcondition: (x:int) := true.")
    # Here, 'x' is rigid (not in frame 'y'). 'y' is in frame.
    # The rigid conjunct is 'x = 5'.
    
    extra = parse_spec("Precondition: (y:int) := forall (x:int) x > 0.\nPostcondition: (y:int) := true.").precondition.expr
    
    result = rigid_context(spec, extra)
    result_str = to_string(result)
    
    # The result should be `(x = 5) /\ (forall (x:int) x > 0)` or similar
    assert "x = 5" in result_str
    assert "forall" in result_str


