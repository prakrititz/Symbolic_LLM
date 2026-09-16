from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, BinaryOp, Variable, VariablePreviousState
from FormalLLM.lpl.ast import Skip
from FormalLLM.verification.proof_obligations import ProofObligation

class InitializedSkipLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ skip.
    Obligation: P ∧ (x = x_prev) ∧ ... ⇒ Q
    This applies x = x_prev for every variant x in the specification.
    Constants are ignored.
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        assumptions = [spec.precondition.expr]
        
        for p in spec.postcondition.params:
            if not p.name.isupper():  # Variants are not upper-case
                # construct x = x_prev
                eq_expr = BinaryOp(
                    left=Variable(p.name),
                    op='=',
                    right=VariablePreviousState(p.name)
                )
                assumptions.append(eq_expr)
                
        obligation = ProofObligation(
            assumptions=assumptions,
            goal=spec.postcondition.expr,
            params=list(spec.precondition.params) + list(spec.postcondition.params)
        )
        
        program = Skip()
        
        return RefinementResult(
            program=program,
            obligations=[obligation]
        )
