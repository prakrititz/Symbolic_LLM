from typing import List
from FormalLLM.refinement.graph.node import RefinementNode
from FormalLLM.lspec.ast import *
from FormalLLM.lpl.ast import *

def to_string(node: ASTNode, compact: bool = False) -> str:
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
        if compact:
            return f"[{to_string(node.precondition.expr)}, {to_string(node.postcondition.expr)}]"
        else:
            return f"Precondition: {to_string(node.precondition)}\nPostcondition: {to_string(node.postcondition)}"
    elif isinstance(node, Assignment):
        return f"{node.variable} := {to_string(node.expr)}"
    elif isinstance(node, Skip):
        return "skip"
    elif isinstance(node, SequentialComposition):
        return f"{to_string(node.first, compact=True)} ;\n{to_string(node.second, compact=True)}"
    elif isinstance(node, IfElse):
        return f"if {to_string(node.guard)}:\n  {to_string(node.then_branch, compact=True)}\nelse:\n  {to_string(node.else_branch, compact=True)}"
    elif isinstance(node, While):
        return f"while {to_string(node.guard)}:\n  {to_string(node.body, compact=True)}"
    return str(node)

LAW_DESCRIPTIONS = {
    "assignment": 'parameters: {"variable": "x", "expr": "E"} -- refines to the assignment x := E.',
    "sequential": 'parameters: {"intermediate": "R"} -- splits into [P,R] ; [R,Q].',
    "alternation": 'parameters: {"guard": "G"} -- splits into if G then [P/\\G, Q] else [P/\\~G, Q].',
    "iteration": 'parameters: {"guard": "G", "variant": "V"} -- loop with invariant P, guard G and integer variant V, which must strictly decrease.',
    "skip": 'no parameters -- valid only when P already implies Q.',
    "strengthen_post": 'parameters: {"intermediate_post": "R"} -- replaces Q by a STRICTLY STRONGER R (R => Q). R must not equal Q.',
    "weaken_pre": 'parameters: {"intermediate_pre": "R"} -- replaces P by a STRICTLY WEAKER R (P => R). R must not equal P.',
    "initialized_skip": 'no parameters -- skip, assuming every variant keeps its previous-state value.',
    "flexible_sequential": 'parameters: {"pre1": "A", "post1": "B", "pre2": "C", "post2": "D"} -- splits into [A,B] ; [C,D], requiring P => A, B => C and D => Q.',
}

# Presentation order; anything unlisted is appended alphabetically.
LAW_ORDER = ["assignment", "skip", "initialized_skip", "sequential",
             "flexible_sequential", "alternation", "iteration",
             "strengthen_post", "weaken_pre"]

SYNTAX_HELP = (
    "Expression syntax (this is NOT Python):\n"
    "- conjunction is /\\ and disjunction is \\/   (never && or ||)\n"
    "- negation is ~ ; inequality is <>\n"
    "- comparisons are < <= = > >= ; arithmetic is + - * /\n"
    "- x0 means the value of x in the previous state\n"
    "- there are NO function calls: sqrt, max, abs, min are unavailable\n"
    "- inside a JSON string every backslash must be doubled: "
    'write "a /\\\\ b", not "a /\\ b"\n'
)


def generate_state_prompt(node: RefinementNode,
                          blacklisted_laws: List[str] = None,
                          retry_context: str = "",
                          available_laws: List[str] = None) -> str:
    """
    Generates a prompt for the LLM based on the current Spec,
    adhering to Hoare logic congruence (no ancestor history needed).

    `available_laws` restricts the advertised laws to those the engine has
    actually registered: advertising a law the engine cannot apply only wastes
    retries.
    """
    if blacklisted_laws is None:
        blacklisted_laws = []
    if available_laws is None:
        available_laws = list(LAW_DESCRIPTIONS)

    ordered = [l for l in LAW_ORDER if l in available_laws]
    ordered += sorted(l for l in available_laws
                      if l not in LAW_ORDER and l in LAW_DESCRIPTIONS)
    law_lines = "\n".join(f'- "{name}": {LAW_DESCRIPTIONS[name]}'
                          for name in ordered if name in LAW_DESCRIPTIONS)

    spec_str = to_string(node.specification)

    prompt = f"""You are a formal refinement agent. Your task is to select a refinement law to apply to the following specification.

Specification:
{spec_str}

Available Laws (respond with the law name and its parameters):
{law_lines}

{SYNTAX_HELP}
Every step must make progress: never produce a sub-specification identical to
the one above.

Respond ONLY with valid JSON of the form
{{"law": "<name>", "parameters": {{...}}}}
Do not include markdown formatting or explanations.
"""
    if blacklisted_laws:
        prompt += f"\nThe following laws have been exhausted and must NOT be used: {', '.join(blacklisted_laws)}\n"

    if retry_context:
        prompt += f"\nFeedback from previous attempt:\n{retry_context}\n"

    return prompt
