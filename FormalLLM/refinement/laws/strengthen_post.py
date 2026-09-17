import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import derive as _derive
from FormalLLM.refinement.frame import obligation_params

class StrengthenPostconditionLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ [P, R]
    Obligation: R ⇒ Q
    """
    PARAMS = (("intermediate_post", "expr", "true"),)
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_post = parameters.get('intermediate_post')
        
        if not intermediate_post:
            raise ValueError("StrengthenPostconditionLaw requires 'intermediate_post' parameter.")
            
        # Obligation: R ⇒ Q
        obligation = ProofObligation(
            assumptions=[intermediate_post],
            goal=spec.postcondition.expr,
            params=obligation_params(spec),
            description="the new postcondition must be stronger than the old one: R => Q",
        )
        
        # Create sub-spec: [P, R]
        spec1 = _derive(spec, 
            precondition=copy.deepcopy(spec.precondition),
            postcondition=Definition(
                name=None,
                params=copy.deepcopy(spec.postcondition.params),
                expr=copy.deepcopy(intermediate_post)
            )
        )
        
        return RefinementResult(
            sub_specs=[spec1],
            obligations=[obligation],
            roles=["sub"],
        )

    @classmethod
    def build_program(cls, parameters, children):
        # These laws only reshape the specification; the program is whatever
        # the single child refined to.
        return children["sub"]
