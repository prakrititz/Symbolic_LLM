import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.lpl.ast import SequentialComposition
from FormalLLM.refinement.frame import derive as _derive, rigid_context

class SequentialCompositionLaw(RefinementLaw):
    """
    Implements [P, Q] ↓ [P, R] ; [R, Q]
    No proof obligations generated here.
    """
    PARAMS = (("intermediate", "expr", "true"),)
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        intermediate_expr = parameters.get('intermediate')
        
        if not intermediate_expr:
            raise ValueError("SequentialCompositionLaw requires 'intermediate' parameter.")

        # Carry the precondition's rigid facts into the midpoint. The second
        # half is specified from the intermediate alone, so without this a fact
        # about a variable the program never assigns -- `d > 0` in an integer
        # division, say -- is lost halfway through and the second half cannot be
        # discharged. No declared frame means nothing is known to be rigid and
        # this is a no-op.
        intermediate_expr = rigid_context(spec, intermediate_expr)
            
        # Create sub-spec 1: [P, R]
        spec1 = _derive(spec, 
            precondition=copy.deepcopy(spec.precondition),
            postcondition=Definition(
                name=None,
                params=copy.deepcopy(spec.postcondition.params),
                expr=copy.deepcopy(intermediate_expr)
            )
        )
        
        # Create sub-spec 2: [R, Q]
        spec2 = _derive(spec, 
            precondition=Definition(
                name=None,
                params=copy.deepcopy(spec.precondition.params),
                expr=copy.deepcopy(intermediate_expr)
            ),
            postcondition=copy.deepcopy(spec.postcondition)
        )
        
        return RefinementResult(
            sub_specs=[spec1, spec2],
            roles=["part1", "part2"],
        )

    @classmethod
    def build_program(cls, parameters, children):
        return SequentialComposition(children["part1"], children["part2"])
