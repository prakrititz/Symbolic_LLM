import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition, BinaryOp, UnaryOp

class AlternationLaw(RefinementLaw):
    r"""
    Implements the simplified if-else Alternation Law (Lemma 6.5).
    [P, Q] → if G: [P ∧ G, Q] else: [P ∧ ¬G, Q]
    
    Note: This specific law assumes the guard implicitly covers all cases 
    (G \/ ¬G is a tautology), so it doesn't generate a separate P ⇒ G ∨ ¬G 
    proof obligation like the core Lemma 2.6 would for multiple guards.
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        guard_expr = parameters.get('guard')
        
        if not guard_expr:
            raise ValueError("AlternationLaw requires 'guard' parameter.")
            
        # Create sub-spec 1: [P ∧ G, Q]
        spec1 = Spec(
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=BinaryOp(copy.deepcopy(spec.precondition.expr), '/\\', copy.deepcopy(guard_expr))
            ),
            postcondition=copy.deepcopy(spec.postcondition)
        )
        
        # Create sub-spec 2: [P ∧ ¬G, Q]
        spec2 = Spec(
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=BinaryOp(copy.deepcopy(spec.precondition.expr), '/\\', UnaryOp('~', copy.deepcopy(guard_expr)))
            ),
            postcondition=copy.deepcopy(spec.postcondition)
        )
        
        return RefinementResult(
            sub_specs=[spec1, spec2]
        )
