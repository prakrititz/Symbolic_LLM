from dataclasses import dataclass, field
from typing import List, Optional
from FormalLLM.lspec.ast import Expr, Param

@dataclass
class ProofObligation:
    assumptions: List[Expr]
    goal: Expr
    # Declared parameters of the originating specification. Laws hand these
    # through so the SMT backend can give names their declared sort instead of
    # defaulting every unbound name to Real.
    params: List[Param] = field(default_factory=list)
    #: What this obligation checks, in the law's own terms -- e.g.
    #: "the loop body must preserve the invariant and decrease the variant".
    #: Without it a rejection reaches the model as a bare counterexample and it
    #: cannot tell which of its choices was at fault.
    description: Optional[str] = None
