from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec
from FormalLLM.lpl.ast import Assignment
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.lspec.substitution import substitute

class AssignmentLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ x := E.
    Obligation: P ⇒ Q[x := E]
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        variable = parameters.get('variable')
        expr = parameters.get('expr')
        
        if not variable or not expr:
            raise ValueError("AssignmentLaw requires 'variable' and 'expr' parameters.")
            
        # Compute Q[x := E]
        q_substituted = substitute(spec.postcondition.expr, variable, expr)
        
        # Obligation: P ⇒ Q[x := E]
        obligation = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=q_substituted
        )
        
        program = Assignment(variable, expr)
        
        return RefinementResult(
            program=program,
            obligations=[obligation]
        )
