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

    Obligations: I ∧ ¬G ⇒ Q.
    Sub-specs: [P, I] when I differs from P (the initialisation), and the body
    [I ∧ G ∧ V = V0, I ∧ V < V0].
    """
    # guard and variant have no meaningful default. Defaulting the variant to
    # "0" (as this once did) yields a constant that can never decrease, so the
    # loop body becomes unprovable and the model is told its parameters were
    # wrong rather than that it forgot one.
    PARAMS = (("guard", "expr", None), ("variant", "expr", None),
              ("invariant", "expr", None))
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

        # The invariant is supplied by the model; falling back to the
        # precondition reproduces the core Lemma 2.7 form.
        invariant_expr = parameters.get('invariant')
        if invariant_expr is None:
            invariant_expr = spec.precondition.expr
        else:
            # Carry the precondition's rigid facts into the invariant. The loop
            # body is specified from the invariant alone, so without this a fact
            # like `e > 0` -- about a variable the program never assigns -- is
            # lost, and the variant-decrease obligation cannot be discharged.
            # No declared frame means nothing is known to be rigid and this is
            # a no-op.
            invariant_expr = rigid_context(spec, invariant_expr)
        
        # Obligation: I ∧ ¬G ⇒ Q
        obligation = ProofObligation(
            assumptions=[copy.deepcopy(invariant_expr), UnaryOp('~', copy.deepcopy(guard_expr))],
            goal=copy.deepcopy(spec.postcondition.expr),
            params=obligation_params(spec),
            description="on exit the invariant and the negated guard must imply the postcondition: I /\ ~G => Q",
        )
        
        # V0 is the variant evaluated in the pre-state of the body
        v0_expr = to_previous_state(variant_expr)
        
        # Sub-spec precondition: I ∧ G ∧ (V = V0)
        pre_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', copy.deepcopy(guard_expr))
        # Capture the variant's pre-state value. Without the V = V0 conjunct, V0 is an
        # unconstrained logical constant and no loop body can ever be verified.
        pre_expr = BinaryOp(pre_expr, '/\\',
                            BinaryOp(copy.deepcopy(variant_expr), '=', copy.deepcopy(v0_expr)))

        # Sub-spec postcondition: I ∧ (V < V0)
        v_decreases = BinaryOp(copy.deepcopy(variant_expr), '<', v0_expr)
        post_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', v_decreases)
        
        body_spec = _derive(spec, 
            precondition=Definition(None, copy.deepcopy(spec.precondition.params), pre_expr),
            postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), post_expr)
        )
        
        sub_specs = []
        roles = []
        
        # If P != I we need an initialisation sub-spec [P, I] to establish the
        # invariant before the loop is entered.
        if spec.precondition.expr != invariant_expr:
            init_spec = _derive(spec, 
                precondition=copy.deepcopy(spec.precondition),
                postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), copy.deepcopy(invariant_expr))
            )
            sub_specs.append(init_spec)
            roles.append("init")
            
        sub_specs.append(body_spec)
        roles.append("body")
        
        return RefinementResult(
            sub_specs=sub_specs,
            obligations=[obligation],
            roles=roles,
        )

    @classmethod
    def build_program(cls, parameters, children):
        loop = While(parameters["guard"], children["body"])
        if "init" not in children:
            return loop
        return SequentialComposition(children["init"], loop)
