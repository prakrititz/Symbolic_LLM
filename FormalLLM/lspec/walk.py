"""Single source of truth for AST structure.

Every traversal in the codebase used to re-encode the shape of the AST as its
own ``isinstance`` chain -- substitution, alpha-renaming, free-variable
collection, the Z3 translator, the pretty-printer and the iteration law's
previous-state rewrite all listed the same node types independently. Four of
the six ended their chain with a silent ``copy.deepcopy(node)``, so a node type
they had never heard of was passed through unchanged instead of raising. Adding
a node type therefore meant editing every chain, and forgetting one produced no
error -- just a wrong formula.

This module holds that structure once. A node type declares its fields and how
each should be traversed; ``children``/``rebuild`` then drive every generic
traversal, and an unregistered node type raises :class:`UnknownNodeError` at the
first traversal that touches it rather than being silently copied.

Field kinds:

``NODE``
    A single child AST node, traversed.
``NODES``
    A list of child AST nodes, traversed in order.
``BINDERS``
    A list of :class:`~FormalLLM.lspec.ast.Param` that *bind* names over the
    node's other fields. Traversals that track scope read this to know what
    goes out of scope; it is what makes capture-avoidance generic.
``ATOM``
    A leaf value carried verbatim (a name, an operator, a literal, a type).
``NAME``
    An ``ATOM`` that is a variable reference in its own right -- the array name
    in ``a[i]``. Distinguished from ``ATOM`` so free-variable collection and
    renaming pick it up without special-casing array nodes.
"""

from typing import Any, Callable, Dict, List, Tuple

from .ast import (
    ASTNode, Spec, Definition, Param, QuantifiedExpr, BinaryOp, UnaryOp,
    Variable, Const, Number, BooleanConst, VariablePreviousState,
    ArraySelect, ArraySlice,
)

NODE = "node"
NODES = "nodes"
BINDERS = "binders"
ATOM = "atom"
NAME = "name"

FieldSpec = Tuple[str, str]


class UnknownNodeError(TypeError):
    """Raised when a traversal meets a node type that never registered here."""

    def __init__(self, node: Any):
        super().__init__(
            f"{type(node).__name__} is not registered in lspec.walk. "
            f"Register it with walk.register() so every traversal handles it; "
            f"see the module docstring."
        )
        self.node = node


_SCHEMA: Dict[type, Tuple[FieldSpec, ...]] = {}


def register(node_type: type, fields: Tuple[FieldSpec, ...]) -> None:
    """Declare the traversable structure of ``node_type``.

    Call this once per AST node type. ``fields`` lists ``(attribute, kind)`` in
    constructor order -- ``rebuild`` passes them positionally.
    """
    for attr, kind in fields:
        if kind not in (NODE, NODES, BINDERS, ATOM, NAME):
            raise ValueError(f"unknown field kind {kind!r} for {node_type.__name__}.{attr}")
    _SCHEMA[node_type] = fields


def schema_of(node: Any) -> Tuple[FieldSpec, ...]:
    """The field schema for ``node``, or raise :class:`UnknownNodeError`."""
    try:
        return _SCHEMA[type(node)]
    except KeyError:
        raise UnknownNodeError(node) from None


def is_registered(node: Any) -> bool:
    return type(node) in _SCHEMA


def children(node: ASTNode) -> List[ASTNode]:
    """Immediate child nodes of ``node``, in field order.

    ``BINDERS`` params are not children: they are binding occurrences, not
    sub-expressions, and every traversal that cares about them handles them
    through :func:`binders_of` instead.
    """
    out: List[ASTNode] = []
    for attr, kind in schema_of(node):
        value = getattr(node, attr)
        if kind == NODE:
            out.append(value)
        elif kind == NODES:
            out.extend(value)
    return out


def binders_of(node: ASTNode) -> List[Param]:
    """Params bound by ``node`` over its own subtree (empty for most nodes)."""
    out: List[Param] = []
    for attr, kind in schema_of(node):
        if kind == BINDERS:
            out.extend(getattr(node, attr))
    return out


def names_of(node: ASTNode) -> List[str]:
    """Bare name references carried by ``node`` itself (the ``NAME`` fields)."""
    return [getattr(node, attr) for attr, kind in schema_of(node) if kind == NAME]


def rebuild(node: ASTNode, **overrides: Any) -> ASTNode:
    """A new node of the same type, with the named fields replaced.

    Fields not overridden are carried across by reference; callers that need
    deep independence copy before passing in. Constructor arguments are passed
    positionally in schema order, so the schema must list fields in the order
    the dataclass declares them.
    """
    fields = schema_of(node)
    known = {attr for attr, _ in fields}
    unknown = set(overrides) - known
    if unknown:
        raise ValueError(
            f"{type(node).__name__} has no field(s) {sorted(unknown)}; "
            f"known fields are {sorted(known)}"
        )
    args = [overrides.get(attr, getattr(node, attr)) for attr, _ in fields]
    return type(node)(*args)


def map_children(node: ASTNode, fn: Callable[[ASTNode], ASTNode]) -> ASTNode:
    """Rebuild ``node`` with ``fn`` applied to each immediate child node.

    ``BINDERS``, ``ATOM`` and ``NAME`` fields are untouched -- a caller that
    needs to rewrite those does so explicitly via :func:`rebuild`, because
    renaming a binder is a scope change and must be a deliberate act.
    """
    overrides: Dict[str, Any] = {}
    for attr, kind in schema_of(node):
        value = getattr(node, attr)
        if kind == NODE:
            overrides[attr] = fn(value)
        elif kind == NODES:
            overrides[attr] = [fn(child) for child in value]
    return rebuild(node, **overrides)


# --- L_spec ---------------------------------------------------------------
# Field order matches each dataclass's constructor; rebuild() relies on it.

register(Spec, (("precondition", NODE), ("postcondition", NODE), ("frame", ATOM)))
register(Definition, (("name", ATOM), ("params", BINDERS), ("expr", NODE)))
register(Param, (("name", ATOM), ("type_", ATOM)))
register(QuantifiedExpr, (("quantifier", ATOM), ("params", BINDERS), ("expr", NODE)))
register(BinaryOp, (("left", NODE), ("op", ATOM), ("right", NODE)))
register(UnaryOp, (("op", ATOM), ("expr", NODE)))
register(Variable, (("name", NAME),))
register(Const, (("name", NAME),))
register(Number, (("value", ATOM),))
register(BooleanConst, (("value", ATOM),))
register(VariablePreviousState, (("name", ATOM),))
register(ArraySelect, (("array", NAME), ("index", NODE)))
register(ArraySlice, (("array", NAME), ("start", NODE), ("end", NODE)))
