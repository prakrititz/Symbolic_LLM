import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import derive as _derive
from FormalLLM.refinement.frame import obligation_params

class WeakenPreconditionLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ [R, Q]
    Obligation: P ⇒ R
    """
    PARAMS = (("intermediate_pre", "expr", "true"),)
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_pre = parameters.get('intermediate_pre')
        
        if not intermediate_pre:
            raise ValueError("WeakenPreconditionLaw requires 'intermediate_pre' parameter.")
            
        # Obligation: P ⇒ R
        obligation = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=intermediate_pre,
            params=obligation_params(spec),
            description="the new precondition must be weaker than the old one: P => R",
        )
        
        # Create sub-spec: [R, Q]
        spec1 = _derive(spec, 
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=copy.deepcopy(intermediate_pre)
            ),
            postcondition=copy.deepcopy(spec.postcondition)
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
