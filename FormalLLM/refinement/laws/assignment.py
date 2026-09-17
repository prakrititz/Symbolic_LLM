from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec
from FormalLLM.lpl.ast import Assignment
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.lspec.substitution import substitute
from FormalLLM.refinement.frame import check_assignable
from FormalLLM.refinement.frame import obligation_params

class AssignmentLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ x := E.
    Obligation: P ⇒ Q[x := E]
    """
    PARAMS = (("variable", "name", None), ("expr", "expr", "0"))
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        variable = parameters.get('variable')
        expr = parameters.get('expr')
        
        if not variable or not expr:
            raise ValueError("AssignmentLaw requires 'variable' and 'expr' parameters.")

        # Enforce the frame. Carrying rigid facts into sub-specifications is
        # only sound if nothing can assign to a rigid variable, so this check is
        # what licenses the propagation in frame.rigid_context.
        check_assignable(spec, variable)
            
        # Compute Q[x := E]
        q_substituted = substitute(spec.postcondition.expr, variable, expr)
        
        # Obligation: P ⇒ Q[x := E]
        obligation = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=q_substituted,
            params=obligation_params(spec),
            description="the assignment must establish the postcondition: P => Q[x := E]",
        )
        
        program = Assignment(variable, expr)
        
        return RefinementResult(
            program=program,
            obligations=[obligation]
        )
