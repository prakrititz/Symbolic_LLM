from dataclasses import dataclass
from typing import List
from FormalLLM.lspec.ast import Expr

@dataclass
class ProofObligation:
    assumptions: List[Expr]
    goal: Expr
