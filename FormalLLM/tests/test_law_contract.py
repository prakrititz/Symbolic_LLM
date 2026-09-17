"""Contract every registered refinement law must satisfy.

M2 adds seven laws and M3 adds Traverse. Each one has to declare its
parameters, name its sub-specifications and say how its program is assembled;
miss any of the three and the failure appears far from the cause -- an LLM
proposal recorded as ERROR, or a program that cannot be reconstructed at the
end of an otherwise successful refinement. These tests state the contract once
so a new law is checked the moment it is registered.
"""

import pytest

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.lspec.ast import BinaryOp, Const, Number, UnaryOp, VariablePreviousState
from FormalLLM.llm.prompts import to_string, LAW_DESCRIPTIONS
from FormalLLM.refinement.laws.base import RefinementLaw, RefinementResult
from FormalLLM.refinement.laws.registry import LAWS, law_named, UnknownLawError
from FormalLLM.refinement.laws.iteration import IterationLaw
from FormalLLM.refinement.laws.initialised_iteration import InitialisedIterationLaw
from FormalLLM.refinement.laws.alternation import AlternationLaw


@pytest.mark.parametrize("name", sorted(LAWS))
def test_law_declares_its_parameters(name):
    law_cls = LAWS[name]
    assert law_cls.PARAMS is not None, (
        f"{law_cls.__name__} does not declare PARAMS, so the LLM-response "
        f"parser cannot build its parameters"
    )
    for entry in law_cls.PARAMS:
        assert len(entry) == 3, f"{name}: PARAMS entries are (name, kind, default)"
        _, kind, _ = entry
        assert kind in ("expr", "name"), f"{name}: unknown parameter kind {kind!r}"


@pytest.mark.parametrize("name", sorted(LAWS))
def test_law_is_described_to_the_model(name):
    """A registered law the prompt never mentions can never be chosen."""
    assert name in LAW_DESCRIPTIONS


@pytest.mark.parametrize("name", sorted(LAWS))
def test_declared_parameters_appear_in_the_description(name):
    description = LAW_DESCRIPTIONS[name]
    for param_name, _, _ in LAWS[name].PARAMS:
        assert param_name in description, (
            f"law {name!r} expects parameter {param_name!r} but its prompt "
            f"description never names it"
        )


def test_unknown_law_is_reported_as_a_value_error():
    with pytest.raises(UnknownLawError):
        law_named("teleportation")
    with pytest.raises(ValueError):
        law_named("teleportation")


def test_recursive_result_requires_a_role_per_sub_spec():
    spec = parse_spec("Precondition: (N:int) := N > 0.\nPostcondition: (N:int) := N > 0.")
    with pytest.raises(ValueError, match="name every sub-specification"):
        RefinementResult(sub_specs=[spec, spec], roles=["only_one"])


def test_a_splitting_law_without_a_builder_says_so():
    class HalfFinished(RefinementLaw):
        PARAMS = ()

        def apply(self, spec, parameters):
            return RefinementResult(sub_specs=[spec], roles=["sub"])

    with pytest.raises(NotImplementedError, match="build_program"):
        HalfFinished.build_program({}, {"sub": None})


# --- per-law obligation shape --------------------------------------------
# The engine only ever reports "verified" or "failed", so a law that emits a
# subtly wrong obligation looks exactly like a model that guessed badly. These
# pin the formulas themselves.

SQRT_SPEC = ("Precondition: (N:int) := N >= 0 /\\ i <= N.\n"
             "Postcondition: (N:int) := i >= N.")


def test_iteration_emits_the_exit_obligation():
    """Iteration must prove I /\\ ~G => Q."""
    spec = parse_spec(SQRT_SPEC)
    guard = BinaryOp(Const("i"), "<", Const("N"))
    variant = BinaryOp(Const("N"), "-", Const("i"))

    result = IterationLaw().apply(spec, {"guard": guard, "variant": variant})

    assert len(result.obligations) == 1
    obligation = result.obligations[0]
    assumptions = [to_string(a) for a in obligation.assumptions]
    assert to_string(spec.precondition.expr) in assumptions
    assert to_string(UnaryOp("~", guard)) in assumptions
    assert to_string(obligation.goal) == to_string(spec.postcondition.expr)


def test_iteration_body_pins_the_variant_and_requires_a_decrease():
    """Without ``V = V0`` in the body's precondition, ``V0`` is unconstrained."""
    spec = parse_spec(SQRT_SPEC)
    guard = BinaryOp(Const("i"), "<", Const("N"))
    variant = BinaryOp(Const("N"), "-", Const("i"))

    result = IterationLaw().apply(spec, {"guard": guard, "variant": variant})
    body = result.by_role()["body"]

    v0 = BinaryOp(VariablePreviousState("N"), "-", VariablePreviousState("i"))
    assert to_string(BinaryOp(variant, "=", v0)) in to_string(body.precondition.expr)
    
    # Postcondition requires 0 <= V and V < V0
    assert "0 <= " in to_string(body.postcondition.expr)
    assert to_string(BinaryOp(variant, "<", v0)) in to_string(body.postcondition.expr)


def test_initialised_iteration_generates_init_and_body_roles():
    spec = parse_spec(SQRT_SPEC)
    result = InitialisedIterationLaw().apply(spec, {
        "invariant": BinaryOp(Const("i"), "<=", Const("N")),
        "guard": BinaryOp(Const("i"), "<", Const("N")),
        "variant": BinaryOp(Const("N"), "-", Const("i")),
    })
    # The invariant is explicitly provided, so it generates both init and body.
    assert result.roles == ["init", "body"]


def test_alternation_splits_on_the_guard_and_its_negation():
    spec = parse_spec("Precondition: (A:int) := true.\n"
                      "Postcondition: (A:int) := m >= A.")
    guard = BinaryOp(Const("A"), ">=", Number("0"))

    result = AlternationLaw().apply(spec, {"guard": guard})
    branches = result.by_role()

    assert set(branches) == {"then", "else"}
    assert to_string(guard) in to_string(branches["then"].precondition.expr)
    assert to_string(UnaryOp("~", guard)) in to_string(branches["else"].precondition.expr)
    # Alternation only narrows the precondition; Q is carried into both arms.
    for branch in branches.values():
        assert to_string(branch.postcondition.expr) == to_string(spec.postcondition.expr)


def test_alternation_does_not_mutate_the_specification_it_refines():
    spec = parse_spec("Precondition: (A:int) := true.\n"
                      "Postcondition: (A:int) := m >= A.")
    before = to_string(spec)

    AlternationLaw().apply(spec, {"guard": BinaryOp(Const("A"), ">=", Number("0"))})

    assert to_string(spec) == before
