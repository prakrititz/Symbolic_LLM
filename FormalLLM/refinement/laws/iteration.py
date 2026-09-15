import copy
from typing import Dict, Any
from .base import RefinementLaw, RefinementResult
from FormalLLM.lspec.ast import Spec, Definition, BinaryOp, UnaryOp, Variable, VariablePreviousState, ASTNode
from FormalLLM.verification.proof_obligations import ProofObligation

def to_previous_state(node: ASTNode) -> ASTNode:
    if isinstance(node, Variable):
        return VariablePreviousState(node.name)
    elif isinstance(node, BinaryOp):
        return BinaryOp(to_previous_state(node.left), node.op, to_previous_state(node.right))
    elif isinstance(node, UnaryOp):
        return UnaryOp(node.op, to_previous_state(node.expr))
    return copy.deepcopy(node)

class IterationLaw(RefinementLaw):
    """
    Implements Lemma 2.7: x:[I, Q] ⊑ while G: body
    Requires spec.precondition == I.
    Emits obligation: I ∧ ¬G ⇒ Q
    Returns sub-spec for body: [I ∧ G, I ∧ (V < V0)]
    """
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        guard_expr = parameters.get('guard')
        variant_expr = parameters.get('variant')
        
        if not guard_expr or not variant_expr:
            raise ValueError("IterationLaw requires 'guard' and 'variant' parameters.")
            
        invariant_expr = spec.precondition.expr
        
        # Obligation: I ∧ ¬G ⇒ Q
        obligation = ProofObligation(
            assumptions=[copy.deepcopy(invariant_expr), UnaryOp('~', copy.deepcopy(guard_expr))],
            goal=copy.deepcopy(spec.postcondition.expr)
        )
        
        # V0 is the variant evaluated in the pre-state of the body
        v0_expr = to_previous_state(variant_expr)
        
        # Sub-spec precondition: I ∧ G
        pre_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', copy.deepcopy(guard_expr))
        
        # Sub-spec postcondition: I ∧ (V < V0)
        v_decreases = BinaryOp(copy.deepcopy(variant_expr), '<', v0_expr)
        post_expr = BinaryOp(copy.deepcopy(invariant_expr), '/\\', v_decreases)
        
        body_spec = Spec(
            precondition=Definition(None, copy.deepcopy(spec.precondition.params), pre_expr),
            postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), post_expr)
        )
        
        sub_specs = []
        
        # If P != I, we need an initialization sub-spec [P, I]
        if spec.precondition.expr != invariant_expr:
            init_spec = Spec(
                precondition=copy.deepcopy(spec.precondition),
                postcondition=Definition(None, copy.deepcopy(spec.postcondition.params), copy.deepcopy(invariant_expr))
            )
            sub_specs.append(init_spec)
            
        sub_specs.append(body_spec)
        
        return RefinementResult(
            sub_specs=sub_specs,
            obligations=[obligation]
        )
