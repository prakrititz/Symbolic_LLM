from dataclasses import dataclass, field
from typing import List
from FormalLLM.lspec.ast import Expr, Param

@dataclass
class ProofObligation:
    assumptions: List[Expr]
    goal: Expr
    # Declared parameters of the originating specification. Laws hand these
    # through so the SMT backend can give names their declared sort instead of
    # defaulting every unbound name to Real.
    params: List[Param] = field(default_factory=list)
