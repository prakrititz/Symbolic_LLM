import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition, BinaryOp, UnaryOp, Number
from FormalLLM.lpl.ast import While, SequentialComposition
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import derive as _derive, rigid_context
from FormalLLM.refinement.frame import obligation_params
from FormalLLM.refinement.laws.iteration import to_previous_state

class InitialisedIterationLaw(RefinementLaw):
    """Iteration with an LLM-supplied invariant (paper Table 5, Lemma 6.6).

        x:[P, Q]  ⊑  x:[P, I] ; while G do x:[I ∧ G, I ∧ 0 ≤ V ∧ V < V0]

    Obligations: I ∧ ¬G ⇒ Q.
    Sub-specs: [P, I] (the initialisation), and the body
    [I ∧ G ∧ V = V0, I ∧ 0 ≤ V ∧ V < V0].
    """
    PARAMS = (("guard", "expr", None), ("variant", "expr", None),
              ("invariant", "expr", None))
    
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        guard_expr = parameters.get('guard')
        variant_expr = parameters.get('variant')
        invariant_expr = parameters.get('invariant')
        
        missing = [n for n, v in (("guard", guard_expr), ("variant", variant_expr), ("invariant", invariant_expr))
                   if v is None]
        if missing:
            raise ValueError(
                f"initialised_iteration requires {' and '.join(missing)}."
            )

        invariant_expr = rigid_context(spec, invariant_expr)
        
        # Obligation: I ∧ ¬G ⇒ Q
        obligation = ProofObligation(
            assumptions=[copy.deepcopy(invariant_expr), UnaryOp('~', copy.deepcopy(guard_expr))],
            goal=copy.deepcopy(spec.postcondition.expr),
            params=obligation_params(spec),
            description="on exit the invariant and the negated guard must imply the postcondition: I /\\ ~G => Q",
        )
        
        # V0 is the variant evaluated in the pre-state of the body
        v0_expr = to_previous_state(variant_expr)
        
        # Sub-spec precondition: I ∧ G ∧ (V = V0)
        pre_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', copy.deepcopy(guard_expr))
        pre_expr = BinaryOp(pre_expr, '/\\',
                            BinaryOp(copy.deepcopy(variant_expr), '=', copy.deepcopy(v0_expr)))

        # Sub-spec postcondition: I ∧ 0 ≤ V ∧ (V < V0)
        zero = Number("0")
        v_lower_bound = BinaryOp(zero, '<=', copy.deepcopy(variant_expr))
        v_decreases = BinaryOp(copy.deepcopy(variant_expr), '<', v0_expr)
        variant_cond = BinaryOp(v_lower_bound, '/\\', v_decreases)
        post_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', variant_cond)
        
        body_spec = _derive(spec, 
            precondition=Definition(None, copy.deepcopy(spec.precondition.params), pre_expr),
            postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), post_expr)
        )
        
        init_spec = _derive(spec, 
            precondition=copy.deepcopy(spec.precondition),
            postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), copy.deepcopy(invariant_expr))
        )
        
        return RefinementResult(
            sub_specs=[init_spec, body_spec],
            obligations=[obligation],
            roles=["init", "body"],
        )

    @classmethod
    def build_program(cls, parameters, children):
        return SequentialComposition(children["init"], While(parameters["guard"], children["body"]))
