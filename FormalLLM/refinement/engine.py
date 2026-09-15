from typing import Dict, Any, Type
from FormalLLM.lspec.ast import Spec
from .laws.base import RefinementLaw, RefinementResult
from .laws.assignment import AssignmentLaw
from .laws.skip import SkipLaw
from .laws.sequential import SequentialCompositionLaw
from .laws.alternation import AlternationLaw
from .laws.iteration import IterationLaw
from FormalLLM.verification.z3_backend import verify_obligation, VerificationResult

class VerificationError(Exception):
    pass

class RefinementEngine:
    def __init__(self):
        self.laws: Dict[str, Type[RefinementLaw]] = {
            "assignment": AssignmentLaw,
            "skip": SkipLaw,
            "sequential": SequentialCompositionLaw,
            "alternation": AlternationLaw,
            "iteration": IterationLaw,
        }

    def register_law(self, name: str, law_cls: Type[RefinementLaw]):
        self.laws[name] = law_cls

    def apply(self, spec: Spec, law_name: str, parameters: Dict[str, Any]) -> RefinementResult:
        if law_name not in self.laws:
            raise ValueError(f"Unknown refinement law: {law_name}")
            
        law = self.laws[law_name]()
        result = law.apply(spec, parameters)
        
        # Verify obligations
        for obligation in result.obligations:
            status, msg = verify_obligation(obligation)
            if status == VerificationResult.FAILED:
                raise VerificationError(f"Refinement invalid. {msg}")
            elif status == VerificationResult.UNKNOWN:
                raise VerificationError(f"Refinement verification unknown. {msg}")
                
        return result
