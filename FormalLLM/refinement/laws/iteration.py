import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec import walk
from FormalLLM.lspec.ast import Spec, Definition, BinaryOp, UnaryOp, Variable, Const, VariablePreviousState, ASTNode
from FormalLLM.lpl.ast import While, SequentialComposition
from FormalLLM.verification.proof_obligations import ProofObligation
from FormalLLM.refinement.frame import derive as _derive, rigid_context
from FormalLLM.refinement.frame import obligation_params

def to_previous_state(node: ASTNode) -> ASTNode:
    """Rewrite every variable in ``node`` to its previous-state twin (``x`` -> ``x0``).

    Note: names coming from LLM-supplied expressions are resolved to Const
    (they are not bound by any params list), so both cases must be handled or
    the variant-decrease obligation degenerates to `V < V`, i.e. false.

    Structure comes from :mod:`lspec.walk`. The previous version enumerated
    BinaryOp and UnaryOp explicitly and deep-copied anything else, so a variant
    expression containing any other compound node -- an array select, say --
    was returned with its variables *unrewritten*, again degenerating the
    obligation to `V < V`.
    """
    if isinstance(node, (Variable, Const)):
        return VariablePreviousState(node.name)
    return walk.map_children(node, to_previous_state)

class IterationLaw(RefinementLaw):
    """Iteration with an LLM-supplied invariant (paper Table 5, Lemma 6.6).

        x:[P, Q]  ⊑  x:[P, I] ; while G do x:[I ∧ G, I ∧ V < V0]

    The invariant is a *parameter*, not the precondition. Previously this law
    read ``invariant = spec.precondition.expr``, which pinned I to P and left
    the initialisation branch below unreachable (``P != invariant`` could never
    be true). That restricted the law to specifications whose precondition
    already happens to be a loop invariant, and forced every other problem
    through a `sequential` step whose intermediate the model had to guess
    exactly right -- which is the one move no model in Study 3 found.

    Omitting `invariant` keeps the old behaviour (I = P), so existing scripted
    refinements and tests are unaffected.

    Obligations: P ∧ ¬G ⇒ Q.
    Sub-specs: [P ∧ G ∧ V = V0, P ∧ 0 ≤ V ∧ V < V0].
    """
    # guard and variant have no meaningful default. Defaulting the variant to
    # "0" (as this once did) yields a constant that can never decrease, so the
    # loop body becomes unprovable and the model is told its parameters were
    # wrong rather than that it forgot one.
    PARAMS = (("guard", "expr", None), ("variant", "expr", None))
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        guard_expr = parameters.get('guard')
        variant_expr = parameters.get('variant')
        
        missing = [n for n, v in (("guard", guard_expr), ("variant", variant_expr))
                   if v is None]
        if missing:
            raise ValueError(
                f"iteration requires {' and '.join(missing)}: the guard is the "
                f"loop condition, and the variant is an expression that must "
                f"strictly decrease on every iteration so the loop terminates."
            )

        # In pure Iteration, the invariant is exactly the precondition.
        invariant_expr = spec.precondition.expr
        
        # Obligation: P ∧ ¬G ⇒ Q
        obligation = ProofObligation(
            assumptions=[copy.deepcopy(invariant_expr), UnaryOp('~', copy.deepcopy(guard_expr))],
            goal=copy.deepcopy(spec.postcondition.expr),
            params=obligation_params(spec),
            description="on exit the precondition (invariant) and the negated guard must imply the postcondition: P /\\ ~G => Q",
        )
        
        # V0 is the variant evaluated in the pre-state of the body
        v0_expr = to_previous_state(variant_expr)
        
        # Sub-spec precondition: I ∧ G ∧ (V = V0)
        pre_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', copy.deepcopy(guard_expr))
        # Capture the variant's pre-state value. Without the V = V0 conjunct, V0 is an
        # unconstrained logical constant and no loop body can ever be verified.
        pre_expr = BinaryOp(pre_expr, '/\\',
                            BinaryOp(copy.deepcopy(variant_expr), '=', copy.deepcopy(v0_expr)))

        # Sub-spec postcondition: P ∧ 0 ≤ V ∧ (V < V0)
        from FormalLLM.lspec.ast import Number
        zero = Number("0")
        v_lower_bound = BinaryOp(zero, '<=', copy.deepcopy(variant_expr))
        v_decreases = BinaryOp(copy.deepcopy(variant_expr), '<', v0_expr)
        variant_cond = BinaryOp(v_lower_bound, '/\\', v_decreases)
        post_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', variant_cond)
        
        body_spec = _derive(spec, 
            precondition=Definition(None, copy.deepcopy(spec.precondition.params), pre_expr),
            postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), post_expr)
        )
        
        return RefinementResult(
            sub_specs=[body_spec],
            obligations=[obligation],
            roles=["body"],
        )

    @classmethod
    def build_program(cls, parameters, children):
        return While(parameters["guard"], children["body"])
