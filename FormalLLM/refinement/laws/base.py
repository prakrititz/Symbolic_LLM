from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from FormalLLM.lspec.ast import Spec, Expr
from FormalLLM.lpl.ast import ProgramNode
from FormalLLM.verification.proof_obligations import ProofObligation

class RefinementResult:
    def __init__(self, 
                 program: Optional[ProgramNode] = None, 
                 sub_specs: Optional[List[Spec]] = None, 
                 obligations: Optional[List[ProofObligation]] = None):
        self.program = program
        self.sub_specs = sub_specs or []
        self.obligations = obligations or []

class RefinementLaw(ABC):
    @abstractmethod
    def apply(self, spec: Spec, parameters: Dict[str, Any]) -> RefinementResult:
        """
        Applies the refinement law to the given specification.
        Returns a RefinementResult containing generated code, new sub-specifications, 
        and proof obligations.
        """
        pass
