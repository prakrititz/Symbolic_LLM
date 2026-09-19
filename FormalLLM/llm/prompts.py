from typing import List
from FormalLLM.refinement.graph.node import RefinementNode
from FormalLLM.lspec import walk
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
    # No silent fallback: `str(node)` rendered an unhandled node as its
    # dataclass repr, which then travelled into the LLM prompt and into
    # `spec_key`, where the progress guard compares specifications as strings.
    # Fail loudly instead.
    raise walk.UnknownNodeError(node)

LAW_DESCRIPTIONS = {
    "assignment": 'parameters: {"variable": "x", "expr": "E"} -- refines to the assignment x := E.',
    "sequential": 'parameters: {"intermediate": "R"} -- splits into [P,R] ; [R,Q]. Note: R must be a BARE boolean expression (e.g. "x > 0"), not a full Spec/Definition.',
    "alternation": 'parameters: {"guard": "G"} -- splits into if G then [P/\\G, Q] else [P/\\~G, Q].',
    "iteration": 'parameters: {"guard": "G", "variant": "V"} '
                 '-- builds while G do (body). Valid ONLY when the precondition '
                 'is already the loop invariant. V is an expression that strictly '
                 'decreases each iteration.',
    "initialised_iteration": 'parameters: {"invariant": "I", "guard": "G", "variant": "V"} '
                             '-- builds x:[P,I] ; while G do (body). I is the loop invariant: '
                             'it must hold before and after every iteration, and I together '
                             'with the negated guard must imply the postcondition. V is an '
                             'expression that strictly decreases each iteration. '
                             'Supplying I lets one step introduce both the initialisation and the loop.',
    "skip": 'no parameters -- valid only when P already implies Q.',
    "strengthen_post": 'parameters: {"intermediate_post": "R"} -- replaces Q by a STRICTLY STRONGER R (R => Q). R must not equal Q. Note: R must be a BARE boolean expression (e.g. "x > 0").',
    "weaken_pre": 'parameters: {"intermediate_pre": "R"} -- replaces P by a STRICTLY WEAKER R (P => R). R must not equal P. Note: R must be a BARE boolean expression (e.g. "x > 0").',
    "initialized_skip": 'no parameters -- skip, assuming every variant keeps its previous-state value.',
    "flexible_sequential": 'parameters: {"pre1": "A", "post1": "B", "pre2": "C", "post2": "D"} -- splits into [A,B] ; [C,D], requiring P => A, B => C and D => Q. Note: Parameters must be BARE boolean expressions.',
}

# Presentation order; anything unlisted is appended alphabetically.
LAW_ORDER = ["assignment", "skip", "initialized_skip", "sequential",
             "flexible_sequential", "alternation", "iteration", "initialised_iteration",
             "strengthen_post", "weaken_pre"]

SYNTAX_HELP = (
    "Expression syntax (this is NOT Python):\n"
    "- conjunction: write &&    disjunction: write ||    negation: write !\n"
    "  L_spec spells these /\\ and \\/ and ~, but a backslash inside a JSON\n"
    "  string has to be doubled and that is easy to get wrong, so the\n"
    "  backslash-free spellings above are preferred and always accepted.\n"
    "- comparisons are < <= = > >= and != ; arithmetic is + - * /\n"
    "- no ternary/conditional expressions exist in this language.\n"
    "- x0 means the value of x in the previous state. Note that x0 is unconstrained unless the precondition says something about x.\n"
    "- there are NO function calls: sqrt, max, abs, min are unavailable.\n"
    "  A square root must be reached by refining to a loop, never by sqrt().\n"
)


def generate_state_prompt(node: RefinementNode,
                          blacklisted_laws: List[str] = None,
                          history_context: str = "",
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

    # State the frame explicitly. Without it the model proposes assignments to
    # variables it is not allowed to change -- measured on gpt-oss-120b, which
    # spent calls trying to assign to N -- and cannot tell which names are
    # rigid.
    frame = getattr(node.specification, "frame", None)
    frame_note = ""
    if frame:
        names = ", ".join(getattr(v, "name", str(v)) for v in frame)
        frame_note = (
            f"\nYou may ONLY assign to: {names}.\n"
            "Every other name is fixed and must not be assigned; whatever the "
            "precondition says about those names stays true throughout, so you "
            "may rely on it.\n"
        )

    prompt = f"""You are a formal refinement agent. Your task is to select a refinement law to apply to the following specification.

Specification:
{spec_str}

{frame_note}
Available Laws (respond with the law name and its parameters):
{law_lines}

{SYNTAX_HELP}
Every step must make progress: never produce a sub-specification identical to
the one above.

Respond ONLY with valid JSON of the form
{{"law": "<name>", "parameters": {{...}}, "rationale": "..."}}
Do not include markdown formatting or explanations.
"""
    if blacklisted_laws:
        prompt += f"\nThe following laws have been exhausted and must NOT be used: {', '.join(blacklisted_laws)}\n"

    if history_context:
        prompt += f"\n{history_context}\n"

    return prompt

def generate_law_selection_prompt(node: RefinementNode,
                                  blacklisted_laws: List[str] = None,
                                  available_laws: List[str] = None) -> str:
    """Turn 1: Asks the LLM to select a law and provide its rationale."""
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

    frame = getattr(node.specification, "frame", None)
    frame_note = ""
    if frame:
        names = ", ".join(getattr(v, "name", str(v)) for v in frame)
        frame_note = (
            f"\nYou may ONLY assign to: {names}.\n"
            "Every other name is fixed and must not be assigned; whatever the "
            "precondition says about those names stays true throughout.\n"
        )

    prompt = f"""You are a formal refinement agent. Your task is to select a refinement law to apply to the following specification.

Specification:
{spec_str}
{frame_note}
Available Laws:
{law_lines}

Every step must make progress: never choose a law that will reproduce a sub-specification identical to the one above.

Respond ONLY with valid JSON of the form:
{{
  "law": "<name>",
  "rationale": "<step-by-step reasoning for choosing the law>"
}}
Do not include markdown formatting or explanations outside the JSON.
"""
    if blacklisted_laws:
        prompt += f"\nThe following laws have been exhausted and must NOT be used: {', '.join(blacklisted_laws)}\n"

    return prompt

def generate_parameter_synthesis_prompt(node: RefinementNode, law: str, history_context: str = "") -> str:
    from FormalLLM.refinement.laws.registry import law_named
    
    spec = node.specification
    
    prompt = ""
    if history_context:
        prompt += f"[retry — law: {law}, prior attempts failed (see feedback below)]\n\n"
    else:
        prompt += f"[fresh attempt — law: {law}]\n\n"
        
    prompt += "We have decided to apply the law '{}' to the following specification:\n".format(law)
    spec_str = to_string(node.specification)
    
    frame = getattr(node.specification, "frame", None)
    frame_note = ""
    if frame:
        names = ", ".join(getattr(v, "name", str(v)) for v in frame)
        frame_note = f"\nYou may ONLY assign to: {names}.\n"
        
    law_desc = LAW_DESCRIPTIONS.get(law, "")
    
    # Obligation hints to assist parameter synthesis
    hint = ""
    if law == "initialised_iteration":
        post_str = to_string(node.specification.postcondition) if hasattr(node.specification, "postcondition") else "Q"
        hint = f"""
Obligations for {law}:
1. The invariant (I) must be established by the initialization from the Precondition.
2. The invariant and negated guard must imply the Postcondition: I /\\ ~G => {post_str}
3. The variant (V) must be strictly decreasing and bounded below by 0: 0 <= V
"""
    elif law == "iteration":
        post_str = to_string(node.specification.postcondition) if hasattr(node.specification, "postcondition") else "Q"
        hint = f"""
Obligations for {law}:
1. The precondition is the invariant. Along with the negated guard, it must imply the Postcondition: P /\\ ~G => {post_str}
2. The variant (V) must be strictly decreasing and bounded below by 0: 0 <= V
"""
    elif law == "strengthen_post":
        hint = """
CRITICAL FORMATTING NOTE:
The "intermediate_post" parameter must be a BARE boolean expression.
Example: {"intermediate_post": "x >= 0 && x <= N"}
DO NOT include full specification syntax (like (N:float) := ...). Just provide the condition.
"""
    elif law == "weaken_pre":
        hint = """
CRITICAL FORMATTING NOTE:
The "intermediate_pre" parameter must be a BARE boolean expression.
Example: {"intermediate_pre": "x >= 0 && x <= N"}
DO NOT include full specification syntax (like (N:float) := ...). Just provide the condition.
"""
    elif law == "sequential":
        hint = """
CRITICAL FORMATTING NOTE:
The "intermediate" parameter must be a BARE boolean expression.
Example: {"intermediate": "x >= 0 && x <= N"}
DO NOT include full specification syntax (like (N:float) := ...). Just provide the condition.
"""
    elif law == "flexible_sequential":
        hint = """
CRITICAL FORMATTING NOTE:
The parameters ("pre1", "post1", "pre2", "post2") must be BARE boolean expressions.
Example: {"pre1": "x >= 0", "post1": "x <= N", "pre2": "x >= 0", "post2": "x <= N"}
DO NOT include full specification syntax (like (N:float) := ...). Just provide the condition.
"""

    prompt += f"""You are a formal refinement agent. You have chosen to apply the law '{law}' to the following specification.

Specification:
{spec_str}
{frame_note}
Law: "{law}": {law_desc}
{hint}
{SYNTAX_HELP}

Respond ONLY with valid JSON of the form:
{{
  "parameters": {{...}},
  "rationale": "<step-by-step algebraic reasoning to derive the parameters>"
}}
Do not include markdown formatting or explanations outside the JSON.
"""
    if history_context:
        prompt += f"\n{history_context}\n\nReview the failed attempts above and choose DIFFERENT, valid parameters.\n"
    return prompt
