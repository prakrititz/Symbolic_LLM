from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec
from FormalLLM.lpl.ast import Skip
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import obligation_params

class SkipLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ skip.
    Obligation: P ⇒ Q
    """
    PARAMS = ()
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        
        # Obligation: P ⇒ Q
        obligation = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=spec.postcondition.expr,
            params=obligation_params(spec),
            description="skip is only valid when the precondition already implies the postcondition: P => Q",
        )
        
        program = Skip()
        
        return RefinementResult(
            program=program,
            obligations=[obligation]
        )
