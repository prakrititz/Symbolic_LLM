from typing import Dict, Any, Type
from FormalLLM.lspec.ast import Spec
from .laws.base import RefinementLaw, RefinementResult
from .laws.registry import LAWS
from FormalLLM.verification.z3_backend import verify_obligation, VerificationResult

class VerificationError(Exception):
    pass

class RefinementEngine:
    def __init__(self):
        # A per-engine copy of the registry, so a caller may restrict the law
        # set (the benchmark harness does, to make the law set the only
        # variable between arms) without mutating the global registry.
        self.laws: Dict[str, Type[RefinementLaw]] = dict(LAWS)

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
