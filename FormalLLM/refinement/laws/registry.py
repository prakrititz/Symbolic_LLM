"""The set of refinement laws the system knows about, by name.

The name is the contract between the LLM (which proposes ``{"law": "..."}``),
the engine (which applies it), the graph (which reassembles its program) and
the trace (which records it). Keeping one mapping means registering a new law
in one place: :class:`~FormalLLM.refinement.engine.RefinementEngine` and
:class:`~FormalLLM.refinement.graph.graph.RefinementGraph` both read from here.
"""

from typing import Dict, Type

from .base import RefinementLaw
from .assignment import AssignmentLaw
from .skip import SkipLaw
from .sequential import SequentialCompositionLaw
from .alternation import AlternationLaw
from .iteration import IterationLaw
from .strengthen_post import StrengthenPostconditionLaw
from .weaken_pre import WeakenPreconditionLaw
from .initialized_skip import InitializedSkipLaw
from .initialised_iteration import InitialisedIterationLaw
from .flexible_sequential import FlexibleSequentialCompositionLaw

#: Canonical law name -> implementing class.
#:
#: Ordering is Morgan's core laws first, then the derived laws of the paper's
#: Section 6, so that listings read in the order the calculus builds them.
LAWS: Dict[str, Type[RefinementLaw]] = {
    # Core calculus (paper Section 2.2)
    "assignment": AssignmentLaw,
    "skip": SkipLaw,
    "sequential": SequentialCompositionLaw,
    "alternation": AlternationLaw,
    "iteration": IterationLaw,
    "strengthen_post": StrengthenPostconditionLaw,
    "weaken_pre": WeakenPreconditionLaw,
    # Derived / extended laws (paper Section 6.2)
    "initialized_skip": InitializedSkipLaw,
    "initialised_iteration": InitialisedIterationLaw,
    "flexible_sequential": FlexibleSequentialCompositionLaw,
}


class UnknownLawError(ValueError):
    def __init__(self, name: str):
        super().__init__(
            f"Unknown law {name!r}; registered laws are {sorted(LAWS)}"
        )
        self.name = name


def law_named(name: str) -> Type[RefinementLaw]:
    try:
        return LAWS[name]
    except KeyError:
        raise UnknownLawError(name) from None
