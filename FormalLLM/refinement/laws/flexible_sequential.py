import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import derive as _derive

class FlexibleSequentialCompositionLaw(RefinementLaw):
    """
    Implements [P, Q] ⊑ [A, B] ; [C, D]
    Obligations:
      1. P ⇒ A
      2. B ⇒ C
      3. D ⇒ Q
    NB: Lemma 6.2 in the Refine4LLM paper states the third premise as Q ⇒ D.
    However, its own proof derives x:[C,Q] ⊑ x:[C,D] via strengthen-postcondition
    (Lemma 2.1), which requires post' ⇒ post, i.e. D ⇒ Q.
    We use the mathematically sound, proof-correct direction (D ⇒ Q).
    """
    PARAMS = tuple((k, "expr", "true") for k in ("pre1", "post1", "pre2", "post2"))
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        pre1_expr = parameters.get('pre1')
        post1_expr = parameters.get('post1')
        pre2_expr = parameters.get('pre2')
        post2_expr = parameters.get('post2')
        
        if not (pre1_expr and post1_expr and pre2_expr and post2_expr):
            raise ValueError("FlexibleSequentialCompositionLaw requires 'pre1', 'post1', 'pre2', 'post2' parameters.")
            
        params = list(spec.precondition.params) + list(spec.postcondition.params)
        
        # Obligation 1: P ⇒ A
        ob1 = ProofObligation(
            assumptions=[spec.precondition.expr],
            goal=pre1_expr,
            params=params
        )
        
        # Obligation 2: B ⇒ C
        ob2 = ProofObligation(
            assumptions=[post1_expr],
            goal=pre2_expr,
            params=params
        )
        
        # Obligation 3: D ⇒ Q
        ob3 = ProofObligation(
            assumptions=[post2_expr],
            goal=spec.postcondition.expr,
            params=params
        )
        
        # Create sub-spec 1: [A, B]
        spec1 = _derive(spec, 
            precondition=Definition(
                name=None, params=copy.deepcopy(spec.precondition.params), expr=copy.deepcopy(pre1_expr)
            ),
            postcondition=Definition(
                name=None, params=copy.deepcopy(spec.postcondition.params), expr=copy.deepcopy(post1_expr)
            )
        )
        
        # Create sub-spec 2: [C, D]
        spec2 = _derive(spec, 
            precondition=Definition(
                name=None, params=copy.deepcopy(spec.precondition.params), expr=copy.deepcopy(pre2_expr)
            ),
            postcondition=Definition(
                name=None, params=copy.deepcopy(spec.postcondition.params), expr=copy.deepcopy(post2_expr)
            )
        )
        
        return RefinementResult(
            sub_specs=[spec1, spec2],
            obligations=[ob1, ob2, ob3],
            roles=["part1", "part2"],
        )

    @classmethod
    def build_program(cls, parameters, children):
        return SequentialComposition(children["part1"], children["part2"])
