"""Capture-avoiding substitution over L_spec, driven by :mod:`lspec.walk`.

Each function here used to carry its own ``isinstance`` chain listing every
node type. They are now generic: structure comes from the walk registry, so a
node type registered there is handled by all three without further edits, and
one that is not registered raises instead of being silently deep-copied.

Previous-state references (``x0``) are deliberately inert. ``x0`` denotes the
value of ``x`` *before* the step, so it is neither a free occurrence of ``x``
(:func:`get_free_vars` does not report it), nor a target of substitution for
``x``, nor renamed by :func:`alpha_rename`. That is why
``VariablePreviousState.name`` is registered ``ATOM`` rather than ``NAME``.
"""

import copy
from typing import Optional, Set

from . import walk
from .ast import ASTNode, Expr, Param, Variable, Const


def get_free_vars(node: ASTNode, bound_vars: Optional[Set[str]] = None) -> Set[str]:
    """Names occurring free in ``node``.

    A node's own ``NAME`` fields are resolved against the *enclosing* scope;
    its binders extend the scope of its children only. This ordering is what
    makes ``forall (x:int) x > 0`` report no free ``x`` while ``a[x]`` reports
    both ``a`` and ``x``.
    """
    bound = set() if bound_vars is None else bound_vars

    free = {name for name in walk.names_of(node) if name not in bound}

    inner = bound | {p.name for p in walk.binders_of(node)}
    for child in walk.children(node):
        free |= get_free_vars(child, inner)
    return free


def alpha_rename(node: ASTNode, old_name: str, new_name: str) -> ASTNode:
    """Rename every occurrence of ``old_name`` to ``new_name``, binders included.

    This is a whole-subtree rename used to move a binder out of the way before
    substituting; it does not stop at shadowing binders, because the caller's
    intent is precisely to rename the binder as well as its uses.

    The input node is never mutated -- the result is freshly built.
    """
    overrides = {}
    for attr, kind in walk.schema_of(node):
        value = getattr(node, attr)
        if kind == walk.NAME:
            overrides[attr] = new_name if value == old_name else value
        elif kind == walk.BINDERS:
            overrides[attr] = [
                Param(new_name if p.name == old_name else p.name, p.type_)
                for p in value
            ]
        elif kind == walk.NODE:
            overrides[attr] = alpha_rename(value, old_name, new_name)
        elif kind == walk.NODES:
            overrides[attr] = [alpha_rename(c, old_name, new_name) for c in value]
    return walk.rebuild(node, **overrides)


def _fresh_name(base: str, taken: Set[str]) -> str:
    """A variant of ``base`` not in ``taken``.

    The old code used ``f"{base}_fresh"`` unconditionally, which collides as
    soon as two binders in one formula share a name or a spec already mentions
    ``x_fresh``.
    """
    candidate = f"{base}_fresh"
    while candidate in taken:
        candidate += "_"
    return candidate


def substitute(node: ASTNode, var_name: str, replacement: Expr) -> ASTNode:
    """``node[var_name := replacement]``, avoiding capture.

    Substitution stops at a binder for ``var_name`` (the occurrence is
    shadowed). Binders whose names occur free in ``replacement`` are renamed
    apart first, so a replacement expression never has its own free variables
    captured.
    """
    binders = walk.binders_of(node)

    if any(p.name == var_name for p in binders):
        return copy.deepcopy(node)

    if binders:
        # Rename apart any binder that would capture a free variable of the
        # replacement. The rename rebuilds the node, so -- unlike the previous
        # implementation, which assigned `p.name = fresh` straight onto the
        # caller's params list -- the input spec is left untouched.
        repl_free = get_free_vars(replacement)
        taken = repl_free | get_free_vars(node) | {var_name}
        for p in binders:
            if p.name in repl_free:
                fresh = _fresh_name(p.name, taken)
                taken.add(fresh)
                node = alpha_rename(node, p.name, fresh)

    # Base case: a name reference that *is* the variable becomes the
    # replacement outright. Every other node keeps its shape and recurses.
    if isinstance(node, (Variable, Const)) and node.name == var_name:
        return copy.deepcopy(replacement)

    overrides = {}
    for attr, kind in walk.schema_of(node):
        value = getattr(node, attr)
        if kind == walk.NAME and value == var_name:
            # A NAME field holds a bare identifier, not an expression -- the
            # array name in `a[i]`. Only a replacement that is itself an
            # identifier can go there; anything else (`a[i] := b[j] + 1`) has
            # no representation in the AST, so say so rather than silently
            # dropping the substitution, as the previous `isinstance(
            # replacement, str)` guard did (it was never true).
            if isinstance(replacement, (Variable, Const)):
                overrides[attr] = replacement.name
            else:
                raise NotImplementedError(
                    f"cannot substitute {type(replacement).__name__} for the "
                    f"array name {var_name!r} in {type(node).__name__}: only a "
                    f"variable or constant can name an array"
                )
        elif kind == walk.NODE:
            overrides[attr] = substitute(value, var_name, replacement)
        elif kind == walk.NODES:
            overrides[attr] = [substitute(c, var_name, replacement) for c in value]
        elif kind == walk.BINDERS:
            overrides[attr] = copy.deepcopy(value)

    return walk.rebuild(node, **overrides)
