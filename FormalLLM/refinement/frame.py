"""Frame reasoning: what the program may change, and what therefore cannot.

Morgan writes a specification as ``x : [pre, post]``, where ``x`` is the *frame*
-- the list of variables the program is allowed to modify (paper §2.1). Every
other name is **rigid**: no step of the refinement can change it, so whatever
the precondition says about it remains true everywhere inside that refinement.

This matters because a specification loses context as it is decomposed. In the
paper's square-root example the precondition says ``N >= 0 /\\ e > 0``; the loop
body's specification is built from the invariant alone, so ``e > 0`` disappears
-- and without it the body's variant-decrease obligation cannot be discharged,
because Z3 must consider ``e <= 0``. Measured on `gpt-oss-120b`: it proposed the
correct guard and variant and was rejected for exactly this reason.

Carrying the rigid conjuncts forward is sound precisely because the frame says
those variables never change. It is *only* sound if the frame is enforced, which
is why :func:`check_assignable` exists and why an undeclared frame (``None``)
means "assume anything may change" and propagates nothing.
"""

from typing import List, Optional, Sequence

from FormalLLM.lspec.ast import ASTNode, BinaryOp, Expr
from FormalLLM.lspec.substitution import get_free_vars


class FrameViolation(Exception):
    """Raised when a refinement would assign to a variable outside the frame."""


def split_conjunction(expr: Expr) -> List[Expr]:
    """Flatten a conjunction into its conjuncts."""
    if isinstance(expr, BinaryOp) and expr.op == "/\\":
        return split_conjunction(expr.left) + split_conjunction(expr.right)
    return [expr]


def join_conjunction(parts: Sequence[Expr]) -> Optional[Expr]:
    """Rebuild a conjunction from its parts (``None`` if there are none)."""
    if not parts:
        return None
    result = parts[0]
    for part in parts[1:]:
        result = BinaryOp(result, "/\\", part)
    return result


def frame_names(frame) -> set:
    """The names in a frame, which may be Params or bare strings."""
    if not frame:
        return set()
    return {getattr(v, "name", v) for v in frame}


def obligation_params(spec) -> list:
    """Declared params for the SMT backend: the spec's, plus typed frame vars.

    Frame variables are the ones the program assigns, and they are exactly the
    names the precondition's params list does *not* declare. Without their
    declared sort the backend falls back to Real, so an integer program is
    reasoned about over the rationals -- which showed up as a counterexample of
    `q = -9/8` for an integer quotient.
    """
    params = list(spec.precondition.params) + list(spec.postcondition.params)
    for entry in (spec.frame or []):
        if getattr(entry, "type_", None) is not None:
            params.append(entry)
    return params


def rigid_conjuncts(expr: Expr, frame) -> List[Expr]:
    """The conjuncts of ``expr`` that mention no frame variable.

    These are the facts the program cannot invalidate. With no declared frame
    nothing is known to be rigid, so the result is empty and callers behave
    exactly as they did before frames existed.
    """
    if not frame:
        return []
    modifiable = frame_names(frame)
    return [c for c in split_conjunction(expr)
            if not (get_free_vars(c) & modifiable)]


def rigid_context(spec, extra: Optional[Expr] = None) -> Optional[Expr]:
    """The rigid part of ``spec``'s precondition, optionally conjoined with ``extra``.

    Conjuncts already present in ``extra`` are not repeated: a model that
    correctly restates ``e > 0`` in its invariant should not produce
    ``e > 0 /\\ e > 0``.
    """
    from FormalLLM.llm.prompts import to_string

    parts = rigid_conjuncts(spec.precondition.expr, spec.frame)
    if extra is not None:
        already = {to_string(c) for c in split_conjunction(extra)}
        parts = [p for p in parts if to_string(p) not in already]
        parts = parts + [extra]
    return join_conjunction(parts)


def check_assignable(spec, variable: str) -> None:
    """Reject an assignment to a variable the frame does not permit changing.

    Without this the propagation in :func:`rigid_context` would be unsound: a
    fact could be carried past the very step that falsified it.
    """
    if spec.frame is None:
        return
    if variable not in frame_names(spec.frame):
        raise FrameViolation(
            f"cannot assign to {variable!r}: the frame of this specification is "
            f"{spec.frame}, so {variable!r} is rigid and must not change"
        )


def derive(parent, precondition, postcondition) -> ASTNode:
    """A sub-specification of ``parent`` that inherits its frame.

    Laws build sub-specifications by constructing a fresh ``Spec``; without this
    the frame would be dropped at the first refinement step and every law below
    the root would lose its rigid context.
    
    The frame is explicitly copied to avoid sibling branches corrupting each
    other's step-local scope (Lemma 2.8) if they shrink the frame.
    """
    from FormalLLM.lspec.ast import Spec
    frame_copy = list(parent.frame) if parent.frame is not None else None
    return Spec(precondition, postcondition, frame_copy)
