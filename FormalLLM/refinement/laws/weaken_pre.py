import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.verification.proof_obligations import ProofObligation

class WeakenPreconditionLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ [R, Q]
    Obligation: P ⇒ R
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_pre = parameters.get('intermediate_pre')
        
        if not intermediate_pre:
            raise ValueError("WeakenPreconditionLaw requires 'intermediate_pre' parameter.")
            
        # Obligation: P ⇒ R
        obligation = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=intermediate_pre,
            params=list(spec.precondition.params) + list(spec.postcondition.params)
        )
        
        # Create sub-spec: [R, Q]
        spec1 = Spec(
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=copy.deepcopy(intermediate_pre)
            ),
            postcondition=copy.deepcopy(spec.postcondition)
        )
        
        return RefinementResult(
            sub_specs=[spec1],
            obligations=[obligation]
        )
