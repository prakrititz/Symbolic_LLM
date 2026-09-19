import json
import re
from typing import Tuple, Dict, Any

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.laws.registry import law_named


# L_spec writes conjunction as /\ and disjunction as \/. Inside a JSON string a
# single backslash starts an escape, so a model that writes "a /\ b" without
# doubling the backslash sends us `/` followed by a newline (from \n) or `/"`
# (from \"). The result is a parse error that says nothing about whether the
# model chose a sensible refinement. Measured on qwen3.5 against the sqrt
# specification: 3 of its 4 proposals were destroyed this way.
#
# These aliases contain no backslash, so they survive JSON intact. They are a
# convenience of the model-facing parser only; L_spec itself is unchanged and
# still accepts /\ and \/.
#
# The word forms are anchored with \b so an identifier that merely contains one
# -- band, x_or_y, nota -- is left alone. Replacements are plain (non-raw)
# strings because re.sub reads a backslash in the replacement as a group
# reference.
OPERATOR_ALIASES = (
    (r"==", "="),
    (r"!=", "<>"),             # before the `!` rule below
    (r"&&", "/\\\\"),
    (r"\|\|", "\\\\/"),
    (r"\band\b", "/\\\\"),
    (r"\bor\b", "\\\\/"),
    (r"\bnot\b", "~"),
    (r"!(?!=)", "~"),          # `!`, but not `!=`
)

# `/` immediately followed by a newline, carriage return, tab or quote: what an
# undoubled /\ becomes once JSON has decoded the escape.
_MANGLED = re.compile("/[\n\r\t\"]")


def normalise_operators(expr_str: str) -> str:
    """Rewrite backslash-free operator spellings into L_spec syntax."""
    for pattern, replacement in OPERATOR_ALIASES:
        expr_str = re.sub(pattern, replacement, expr_str)
    return expr_str


def looks_json_mangled(expr_str: str) -> bool:
    """True if this expression carries the signature of an unescaped ``/\\``.

    Reported rather than silently repaired: dividing by a parenthesised
    comparison is meaningless, so this is almost certainly a lost operator, but
    guessing the author's intent is worse than telling them what went wrong and
    which spelling avoids it.
    """
    return bool(_MANGLED.search(expr_str))


def parse_expr(expr_str: str):
    if looks_json_mangled(expr_str):
        raise ValueError(
            "this expression looks like a conjunction whose backslash was "
            "eaten by JSON escaping. Use && for /\\ and || for \\/ -- they "
            f"need no backslash and survive JSON intact. Got: {expr_str!r}"
        )
    expr_str = normalise_operators(expr_str)
    # Wrap the expression in a dummy specification to parse it using the existing grammar
    dummy_spec_str = f"Precondition: := {expr_str}.\nPostcondition: := true."
    spec = parse_spec(dummy_spec_str)
    return spec.precondition.expr


def _load_json_key(text: str, key: str) -> Dict[str, Any]:
    """Parse the reply as JSON, or recover the JSON object embedded in prose.

    A reasoning model can spend its whole token budget thinking and return an
    empty `content`, in which case the provider falls back to the reasoning
    channel -- which is prose with the answer somewhere inside it. Rather than
    score that as a malformed reply, find the first balanced {...} that parses
    and has a specific key.
    """
    try:
        candidate = json.loads(text)
        if isinstance(candidate, dict) and key in candidate:
            return candidate
    except json.JSONDecodeError:
        pass

    for start in (i for i, ch in enumerate(text) if ch == "{"):
        depth, in_str, escaped = 0, False, False
        for end in range(start, len(text)):
            ch = text[end]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(candidate, dict) and key in candidate:
                        return candidate
                    break
                    
    # Tolerant Fallback: The JSON might be truncated mid-rationale.
    # Since we moved "law" and "parameters" to the top of the prompt schema, 
    # the data we care about should already be fully formed.
    import re
    if key == "law":
        # Extract "law": "some_law_name"
        match = re.search(r'"law"\s*:\s*"([^"]+)"', text)
        if match:
            return {"law": match.group(1)}
    elif key == "parameters":
        # Extract "parameters": { ... } by finding the start and counting braces
        match = re.search(r'"parameters"\s*:\s*\{', text)
        if match:
            start_idx = match.end() - 1  # Index of the opening '{'
            depth, in_str, escaped = 0, False, False
            for i in range(start_idx, len(text)):
                ch = text[i]
                if in_str:
                    if escaped: escaped = False
                    elif ch == "\\": escaped = True
                    elif ch == '"': in_str = False
                else:
                    if ch == '"': in_str = True
                    elif ch == "{": depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            # We found the matching closing brace!
                            try:
                                params_dict = json.loads(text[start_idx:i+1])
                                return {"parameters": params_dict}
                            except json.JSONDecodeError:
                                break
                            
    raise ValueError(
        f'no JSON object with a "{key}" key found in the reply: {text[:200]!r}'
    )

def _load_json(text: str) -> Dict[str, Any]:
    return _load_json_key(text, "law")


def parse_llm_response(response: str) -> Tuple[str, Dict[str, Any]]:
    """Turn one LLM reply into a (law name, parameters) pair."""
    # Remove markdown code blocks if any
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()

    data = _load_json(response)
    law = data.get("law")
    raw_params = data.get("parameters", {}) or {}

    law_cls = law_named(law)          # raises UnknownLawError (a ValueError)

    if law_cls.PARAMS is None:
        raise ValueError(
            f"{law_cls.__name__} is registered as {law!r} but declares no "
            f"PARAMS, so its parameters cannot be parsed"
        )

    parsed_params: Dict[str, Any] = {}
    for name, kind, default in law_cls.PARAMS:
        raw = raw_params.get(name, default)
        if raw is None and default is None:
            continue
        if kind == "name":
            parsed_params[name] = raw
        elif kind == "expr":
            parsed_params[name] = parse_expr(raw if raw is not None else "true")
        else:
            raise ValueError(
                f"{law_cls.__name__}.PARAMS declares unknown kind {kind!r} "
                f"for parameter {name!r}"
            )

    return law, parsed_params

def parse_law_response(response: str) -> str:
    """Turn one LLM reply into a law name."""
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()

    data = _load_json_key(response, "law")
    law = data.get("law")
    
    # Validate that it exists in the registry
    law_named(law) 
    
    return law

def parse_parameters_response(response: str, law: str) -> Dict[str, Any]:
    """Turn one LLM reply into a parameters dict for a specific law."""
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()

    # We look for "parameters" instead of "law"
    data = _load_json_key(response, "parameters")
    raw_params = data.get("parameters", {}) or {}

    law_cls = law_named(law)

    if law_cls.PARAMS is None:
        raise ValueError(
            f"{law_cls.__name__} is registered as {law!r} but declares no "
            f"PARAMS, so its parameters cannot be parsed"
        )

    parsed_params: Dict[str, Any] = {}
    for name, kind, default in law_cls.PARAMS:
        raw = raw_params.get(name, default)
        if raw is None and default is None:
            continue
        if kind == "name":
            parsed_params[name] = raw
        elif kind == "expr":
            parsed_params[name] = parse_expr(raw if raw is not None else "true")
        else:
            raise ValueError(
                f"{law_cls.__name__}.PARAMS declares unknown kind {kind!r} "
                f"for parameter {name!r}"
            )

    return parsed_params
