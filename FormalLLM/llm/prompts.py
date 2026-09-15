from typing import List
from FormalLLM.refinement.tree import RefinementNode
from FormalLLM.lspec.ast import *

def to_string(node: ASTNode) -> str:
    if isinstance(node, BinaryOp):
        # Add parentheses for safety
        return f"({to_string(node.left)} {node.op} {to_string(node.right)})"
    elif isinstance(node, UnaryOp):
        return f"({node.op}{to_string(node.expr)})"
    elif isinstance(node, Variable):
        return node.name
    elif isinstance(node, Const):
        return node.name
    elif isinstance(node, Number) or isinstance(node, BooleanConst):
        return str(node.value)
    elif isinstance(node, Definition):
        params = "".join(f"({p.name}:{p.type_.__class__.__name__.replace('Type', '').lower()})" for p in node.params)
        return f"{params} := {to_string(node.expr)}"
    elif isinstance(node, QuantifiedExpr):
        params = "".join(f"({p.name}:{p.type_.__class__.__name__.replace('Type', '').lower()})" for p in node.params)
        return f"({node.quantifier} {params} {to_string(node.expr)})"
    elif isinstance(node, VariablePreviousState):
        return f"{node.name}0"
    elif isinstance(node, ArraySelect):
        return f"{node.array}[{to_string(node.index)}]"
    elif isinstance(node, ArraySlice):
        return f"{node.array}[{to_string(node.start)}:{to_string(node.end)}]"
    elif isinstance(node, Spec):
        return f"Precondition: {to_string(node.precondition)}\nPostcondition: {to_string(node.postcondition)}"
    return str(node)

def generate_state_prompt(node: RefinementNode, blacklisted_laws: List[str] = None, retry_context: str = "") -> str:
    """
    Generates a prompt for the LLM based on the current Spec, 
    adhering to Hoare logic congruence (no ancestor history needed).
    """
    if blacklisted_laws is None:
        blacklisted_laws = []
        
    spec_str = to_string(node.specification)
    
    prompt = f"""You are a formal refinement agent. Your task is to select a refinement law to apply to the following specification.

Specification:
{spec_str}

Available Laws:
- assignment: Output JSON with `law: "assignment"` and `parameters: {{"variable": "x", "expr": "E"}}` (where E is code).
- sequential: Output JSON with `law: "sequential"` and `parameters: {{"intermediate": "R"}}` (where R is a logical condition).
- alternation: Output JSON with `law: "alternation"` and `parameters: {{"guard": "G"}}` (where G is a boolean condition).
- iteration: Output JSON with `law: "iteration"` and `parameters: {{"guard": "G", "variant": "V"}}` (where G is condition, V is integer expression).
- skip: Output JSON with `law: "skip"` and no parameters.

Respond ONLY with valid JSON. Do not include markdown formatting or explanations.
"""
    if blacklisted_laws:
        prompt += f"\nThe following laws have been exhausted and must NOT be used: {', '.join(blacklisted_laws)}\n"

    if retry_context:
        prompt += f"\nFeedback from previous attempt:\n{retry_context}\n"

    return prompt
