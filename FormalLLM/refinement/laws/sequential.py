import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition

class SequentialCompositionLaw(RefinementLaw):
    """
    Implements [P, Q] ↓ [P, R] ; [R, Q]
    No proof obligations generated here.
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_expr = parameters.get('intermediate')
        
        if not intermediate_expr:
            raise ValueError("SequentialCompositionLaw requires 'intermediate' parameter.")
            
        # Create sub-spec 1: [P, R]
        spec1 = Spec(
            precondition=copy.deepcopy(spec.precondition),
            postcondition=Definition(
                name=None,
                params=copy.deepcopy(spec.postcondition.params),
                expr=copy.deepcopy(intermediate_expr)
            )
        )
        
        # Create sub-spec 2: [R, Q]
        spec2 = Spec(
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=copy.deepcopy(intermediate_expr)
            ),
            postcondition=copy.deepcopy(spec.postcondition)
        )
        
        return RefinementResult(
            sub_specs=[spec1, spec2]
        )
