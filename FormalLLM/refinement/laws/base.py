from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from FormalLLM.lspec.ast import Spec
from FormalLLM.lpl.ast import ProgramNode, MixNode
from FormalLLM.verification.proof_obligations import ProofObligation


class RefinementResult:
    """What applying a law produced.

    A law is *terminal* if it yields a ``program`` (assignment, skip), and
    *recursive* if it yields ``sub_specs`` to be refined further.

    ``roles`` names each entry of ``sub_specs`` -- ``["part1", "part2"]``,
    ``["then", "else"]``, ``["init", "body"]`` and so on. The names are how the
    graph reassembles a program from refined children, and a law that splits
    must supply one per sub-spec. Role names were previously hard-coded in the
    refiner and in both of the graph's reconstruction methods, so each new law
    meant three synchronised edits in files that knew nothing about it.
    """

    def __init__(self,
                 program: Optional[ProgramNode] = None,
                 sub_specs: Optional[List[Spec]] = None,
                 obligations: Optional[List[ProofObligation]] = None,
                 roles: Optional[List[str]] = None):
        self.program = program
        self.sub_specs = sub_specs or []
        self.obligations = obligations or []
        self.roles = roles or []

        if self.sub_specs and len(self.roles) != len(self.sub_specs):
            raise ValueError(
                f"a recursive law must name every sub-specification: got "
                f"{len(self.sub_specs)} sub_specs but {len(self.roles)} roles "
                f"({self.roles})"
            )

    @property
    def is_terminal(self) -> bool:
        return self.program is not None

    def by_role(self) -> Dict[str, Spec]:
        return dict(zip(self.roles, self.sub_specs))


class RefinementLaw(ABC):
    #: The parameters this law expects from the LLM, as
    #: ``(name, kind, default_source)`` triples. ``kind`` is ``"expr"`` (parsed
    #: as an L_spec expression) or ``"name"`` (kept as a bare identifier).
    #: ``None`` means the law never declared them -- which the LLM-response
    #: parser reports rather than silently treating as "no parameters".
    PARAMS = None

    @abstractmethod
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        """
        Applies the refinement law to the given specification.
        Returns a RefinementResult containing generated code, new sub-specifications,
        and proof obligations.
        """
        pass

    @classmethod
    def build_program(cls,
                      parameters: Dict[str, Any],
                      children: Dict[str, MixNode]) -> MixNode:
        """Assemble this law's program from its refined children.

        ``children`` maps the role names this law's :meth:`apply` returned to
        the program (or, mid-refinement, the residual specification) each child
        node refined to. Terminal laws never need this; recursive laws must
        override it.
        """
        raise NotImplementedError(
            f"{cls.__name__} splits a specification but does not define "
            f"build_program(), so its program cannot be reassembled"
        )
