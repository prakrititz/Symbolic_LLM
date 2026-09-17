"""Oracle arm: replays hand-written, known-good refinement moves.

This establishes the *engine ceiling* for each case -- how well a perfect LLM
could possibly do -- so that LLM failures can be separated from limitations of
the refinement engine itself.
"""
import json
import re
from typing import Dict, List, Tuple

from FormalLLM.llm.provider import LLMProvider


def spec_key(prompt: str) -> Tuple[str, str]:
    pre = re.search(r"^Precondition: (.*)$", prompt, re.M)
    post = re.search(r"^Postcondition: (.*)$", prompt, re.M)
    return (pre.group(1).strip() if pre else "?", post.group(1).strip() if post else "?")


def R(law, **params):
    return json.dumps({"law": law, "parameters": params})


# (precondition, postcondition) -> scripted JSON response
PLAYBOOK: Dict[Tuple[str, str], str] = {
    # A1
    ("(x:int) := (x > 5)", "(x:int) := (x > 0)"): R("skip"),
    # A2
    ("(N:int) := (N >= 0)", "(N:int) := (x = (N + 1))"): R("assignment", variable="x", expr="N + 1"),
    # A3
    ("(A:int)(B:int) := (A > B)", "(A:int)(B:int) := ((m = A) /\ (m > B))"):
        R("assignment", variable="m", expr="A"),
    # B1 root + children
    ("(A:int)(B:int) := True", "(A:int)(B:int) := ((s = (A + B)) /\ (d = (A - B)))"):
        R("sequential", intermediate="s = A + B"),
    ("(A:int)(B:int) := True", "(A:int)(B:int) := (s = (A + B))"):
        R("assignment", variable="s", expr="A + B"),
    ("(A:int)(B:int) := (s = (A + B))", "(A:int)(B:int) := ((s = (A + B)) /\ (d = (A - B)))"):
        R("assignment", variable="d", expr="A - B"),
    # B2 root + branches
    ("(A:int)(B:int) := True", "(A:int)(B:int) := (((m = A) \/ (m = B)) /\ ((m >= A) /\ (m >= B)))"):
        R("alternation", guard="A >= B"),
    ("(A:int)(B:int) := (True /\ (A >= B))", "(A:int)(B:int) := (((m = A) \/ (m = B)) /\ ((m >= A) /\ (m >= B)))"):
        R("assignment", variable="m", expr="A"),
    ("(A:int)(B:int) := (True /\ (~(A >= B)))", "(A:int)(B:int) := (((m = A) \/ (m = B)) /\ ((m >= A) /\ (m >= B)))"):
        R("assignment", variable="m", expr="B"),
    # B3 root + branches
    ("(A:int) := True", "(A:int) := (((y = A) \/ (y = (-A))) /\ (y >= 0))"):
        R("alternation", guard="A >= 0"),
    ("(A:int) := (True /\ (A >= 0))", "(A:int) := (((y = A) \/ (y = (-A))) /\ (y >= 0))"):
        R("assignment", variable="y", expr="A"),
    ("(A:int) := (True /\ (~(A >= 0)))", "(A:int) := (((y = A) \/ (y = (-A))) /\ (y >= 0))"):
        R("assignment", variable="y", expr="-A"),
    # C1
    ("(N:float) := (N >= 0)", "(N:float) := ((x * x) <= N)"):
        R("assignment", variable="x", expr="0"),
    # C3 / C4 loops
    ("(N:int)(i:int) := ((N >= 0) /\ (i = 0))", "(N:int)(i:int) := (i >= N)"):
        R("iteration", guard="i < N", variant="N - i"),
    ("(N:int)(i:int) := (i <= N)", "(N:int)(i:int) := (i = N)"):
        R("iteration", guard="i < N", variant="N - i"),
    # C4 loop body
    ("(N:int)(i:int) := (((i <= N) /\ (i < N)) /\ ((N - i) = (N0 - i0)))",
     "(N:int)(i:int) := ((i <= N) /\ ((N - i) < (N0 - i0)))"):
        R("assignment", variable="i", expr="i + 1"),
    # C3 loop body (i = 0 is pinned into the invariant -- no body can preserve it)
    ("(N:int)(i:int) := ((((N >= 0) /\ (i = 0)) /\ (i < N)) /\ ((N - i) = (N0 - i0)))",
     "(N:int)(i:int) := (((N >= 0) /\ (i = 0)) /\ ((N - i) < (N0 - i0)))"):
        R("assignment", variable="i", expr="i + 1"),
    # --- C5: the paper's motivating example (Figure 2/3) -------------------
    # These replay exactly the refinement `manual_sqrt.py` verifies under Z3:
    # split off an initialisation that establishes the invariant, assign x := 0,
    # then iterate x := x + e while N >= (x+e)^2, with variant N - x*x.
    ("(N:float)(e:float) := ((N >= 0) /\ (e > 0))",
     "(N:float)(e:float) := (((x * x) <= N) /\ (N < ((x + e) * (x + e))))"):
        R("sequential", intermediate="N >= 0 /\ e > 0 /\ x*x <= N /\ x >= 0"),
    # part 1: establish the invariant
    ("(N:float)(e:float) := ((N >= 0) /\ (e > 0))",
     "(N:float)(e:float) := ((N >= 0) /\ ((e > 0) /\ (((x * x) <= N) /\ (x >= 0))))"):
        R("assignment", variable="x", expr="0"),
    # part 2: iterate until the postcondition holds
    ("(N:float)(e:float) := ((N >= 0) /\ ((e > 0) /\ (((x * x) <= N) /\ (x >= 0))))",
     "(N:float)(e:float) := (((x * x) <= N) /\ (N < ((x + e) * (x + e))))"):
        R("iteration", guard="N >= (x+e)*(x+e)", variant="N - x*x"),
    # loop body
    ("(N:float)(e:float) := ((((N >= 0) /\ ((e > 0) /\ (((x * x) <= N) /\ (x >= 0)))) /\ (N >= ((x + e) * (x + e)))) /\ ((N - (x * x)) = (N0 - (x0 * x0))))",
     "(N:float)(e:float) := (((N >= 0) /\ ((e > 0) /\ (((x * x) <= N) /\ (x >= 0)))) /\ ((N - (x * x)) < (N0 - (x0 * x0))))"):
        R("assignment", variable="x", expr="x + e"),
    # --- C3 with an LLM-supplied invariant ---------------------------------
    # Previously unsolvable: the engine pinned the invariant to the
    # precondition, so `i = 0` had to hold at every iteration and no body could
    # preserve it. With the invariant supplied (paper Table 5) the natural
    # `i <= N` works and the case is solved in three moves.
    ("(N:int)(i:int) := ((N >= 0) /\ (i = 0))", "(N:int)(i:int) := (i >= N)"):
        R("iteration", invariant="i <= N", guard="i < N", variant="N - i"),
    ("(N:int)(i:int) := ((N >= 0) /\ (i = 0))",
     "(N:int)(i:int) := ((N >= 0) /\ (i <= N))"): R("skip"),
    ("(N:int)(i:int) := ((((N >= 0) /\ (i <= N)) /\ (i < N)) /\ ((N - i) = (N0 - i0)))",
     "(N:int)(i:int) := (((N >= 0) /\ (i <= N)) /\ ((N - i) < (N0 - i0)))"):
        R("assignment", variable="i", expr="i + 1"),
}


class OracleProvider(LLMProvider):
    """Returns the scripted best move; records specs it has no plan for."""

    def __init__(self):
        self.unmatched: List[Tuple[str, str]] = []
        self.last_meta = {}

    def generate(self, prompt: str) -> str:
        key = spec_key(prompt)
        if key in PLAYBOOK:
            return PLAYBOOK[key]
        self.unmatched.append(key)
        # No known-good move: emit skip so the engine reports honestly.
        return R("skip")
