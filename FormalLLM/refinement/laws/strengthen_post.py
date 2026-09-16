import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.verification.proof_obligations import ProofObligation

class StrengthenPostconditionLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ [P, R]
    Obligation: R ⇒ Q
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_post = parameters.get('intermediate_post')
        
        if not intermediate_post:
            raise ValueError("StrengthenPostconditionLaw requires 'intermediate_post' parameter.")
            
        # Obligation: R ⇒ Q
        obligation = ProofObligation(
            assumptions=[intermediate_post],
            goal=spec.postcondition.expr,
            params=list(spec.precondition.params) + list(spec.postcondition.params)
        )
        
        # Create sub-spec: [P, R]
        spec1 = Spec(
            precondition=copy.deepcopy(spec.precondition),
            postcondition=Definition(
                name=None,
                params=copy.deepcopy(spec.postcondition.params),
                expr=copy.deepcopy(intermediate_post)
            )
        )
        
        return RefinementResult(
            sub_specs=[spec1],
            obligations=[obligation]
        )
