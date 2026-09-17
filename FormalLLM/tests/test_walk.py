"""Guards on the AST traversal registry.

The point of :mod:`FormalLLM.lspec.walk` is that node structure is written down
once. These tests fail when a node type is added without registering it -- the
failure mode M2 (assert, procedures) and M3 (array slices, SwapList) would
otherwise hit silently, since an unregistered node produces a wrong formula
rather than an error at the point it is introduced.
"""

import copy
import inspect

import pytest

from FormalLLM.lspec import ast as lspec_ast
from FormalLLM.lspec import walk
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.substitution import get_free_vars, substitute, alpha_rename
from FormalLLM.lpl import ast as lpl_ast
from FormalLLM.llm.prompts import to_string

#: Base classes that exist to be subclassed, never instantiated as nodes.
ABSTRACT = {lspec_ast.ASTNode, lspec_ast.Expr, lspec_ast.Type, lpl_ast.ProgramNode}


def concrete_node_types():
    for module in (lspec_ast, lpl_ast):
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj in ABSTRACT or obj.__module__ not in (lspec_ast.__name__, lpl_ast.__name__):
                continue
            if issubclass(obj, lspec_ast.Type):
                continue          # types are carried as ATOM payloads, not walked
            if issubclass(obj, lspec_ast.ASTNode):
                yield obj


def test_every_concrete_node_type_is_registered():
    unregistered = sorted(t.__name__ for t in concrete_node_types()
                          if t not in walk._SCHEMA)
    assert not unregistered, (
        f"these AST node types are not registered in lspec.walk: {unregistered}. "
        f"Register each one so substitution, renaming, free-variable collection "
        f"and printing all handle it."
    )


def test_schema_field_order_matches_constructor():
    """``rebuild`` passes fields positionally, so the order must line up."""
    for node_type in concrete_node_types():
        schema = walk._SCHEMA[node_type]
        declared = [f for f in node_type.__dataclass_fields__]
        assert [attr for attr, _ in schema] == declared, (
            f"{node_type.__name__}: walk schema lists "
            f"{[a for a, _ in schema]} but the dataclass declares {declared}"
        )


def test_unregistered_node_raises_rather_than_passing_through():
    class Bogus(lspec_ast.Expr):
        pass

    with pytest.raises(walk.UnknownNodeError):
        walk.children(Bogus())


def test_rebuild_and_map_children_round_trip():
    spec = parse_spec("Precondition: (N:int) := N > 0.\n"
                      "Postcondition: (N:int) := x = N + 1.")
    assert walk.rebuild(spec) == spec
    assert walk.map_children(spec, lambda n: n) == spec


def test_rebuild_rejects_unknown_field():
    with pytest.raises(ValueError, match="no field"):
        walk.rebuild(lspec_ast.Variable("x"), nome="y")


def test_binders_scope_over_children_only():
    spec = parse_spec("Precondition: (N:int) := forall (i:int) i > N.\n"
                      "Postcondition: (N:int) := true.")
    # `i` is bound by the quantifier, `N` by the params list; neither is free.
    assert get_free_vars(spec.precondition) == set()
    quantified = spec.precondition.expr
    assert get_free_vars(quantified) == {"N"}


def test_array_name_is_a_free_variable():
    spec = parse_spec("Precondition: (i:int) := a[i] > 0.\n"
                      "Postcondition: (i:int) := true.")
    assert get_free_vars(spec.precondition.expr) == {"a", "i"}


def test_previous_state_is_not_an_occurrence_of_the_variable():
    """``x0`` is the pre-state value, so it is neither free ``x`` nor substituted."""
    spec = parse_spec("Precondition: (N:int) := x0 < N.\nPostcondition: (N:int) := true.")
    expr = spec.precondition.expr
    assert "x" not in get_free_vars(expr)

    substituted = substitute(expr, "x", lspec_ast.Number("7"))
    assert to_string(substituted) == to_string(expr)

    assert to_string(alpha_rename(expr, "x", "y")) == to_string(expr)


def test_substitute_does_not_mutate_its_input():
    """Regression: the Definition branch renamed the caller's params in place.

    It assigned ``p.name = fresh`` directly onto the params list it was handed,
    leaving the caller holding ``(i_fresh:int) := (i < 10)`` -- a spec whose
    parameter no longer binds the variable in its own body. Downstream, Z3
    stopped seeing ``i`` as a declared int and fell back to an untyped Real.
    """
    spec = parse_spec("Precondition: (i:int) := i > 0.\nPostcondition: (i:int) := i < 10.")
    before = copy.deepcopy(spec)

    replacement = lspec_ast.BinaryOp(lspec_ast.Const("i"), "+", lspec_ast.Number("1"))
    substitute(spec.postcondition, "x", replacement)

    assert spec == before


def test_substitute_avoids_capture_and_picks_a_free_fresh_name():
    """The replacement's free ``i`` must not be captured by the bound ``i``."""
    spec = parse_spec("Precondition: (i:int) := true.\nPostcondition: (i:int) := i > y.")
    replacement = lspec_ast.BinaryOp(lspec_ast.Const("i"), "+", lspec_ast.Number("1"))

    result = substitute(spec.postcondition, "y", replacement)

    # The binder was renamed apart, so the replacement's `i` stays free.
    binder = result.params[0].name
    assert binder != "i"
    assert "i" in get_free_vars(result.expr, {binder})


def test_fresh_name_does_not_collide_with_an_existing_one():
    """``f"{name}_fresh"`` was used unconditionally and could collide."""
    spec = parse_spec("Precondition: (i:int) := true.\n"
                      "Postcondition: (i:int) := i > y /\\ i_fresh > 0.")
    replacement = lspec_ast.Const("i")

    result = substitute(spec.postcondition, "y", replacement)

    binder = result.params[0].name
    assert binder not in ("i", "i_fresh")


def test_array_name_substitution_is_explicit_about_what_it_cannot_do():
    """Previously guarded on ``isinstance(replacement, str)``, never true."""
    spec = parse_spec("Precondition: (i:int) := a[i] > 0.\nPostcondition: (i:int) := true.")
    select = spec.precondition.expr.left

    renamed = substitute(select, "a", lspec_ast.Const("b"))
    assert to_string(renamed) == "b[i]"

    compound = lspec_ast.BinaryOp(lspec_ast.Const("b"), "+", lspec_ast.Number("1"))
    with pytest.raises(NotImplementedError, match="array name"):
        substitute(select, "a", compound)


def test_to_string_raises_on_an_unregistered_node():
    """It used to fall back to ``str(node)``, feeding a repr into the prompt."""
    class Bogus(lspec_ast.Expr):
        pass

    with pytest.raises(walk.UnknownNodeError):
        to_string(Bogus())
