"""Benchmark specifications for the FormalLLM (Refine4LLM) refinement engine.

Each case is written in L_spec as accepted by FormalLLM/lspec/grammar.lark.
`expected` records what a correct refinement should look like, and is used only
for qualitative scoring in the report -- the harness never feeds it to the LLM.
"""

CASES = [
    # ---------------- Tier A: single terminal law ----------------
    dict(
        id="A1-skip",
        tier="A",
        title="Trivially implied postcondition",
        spec="Precondition: (x:int) := x > 5.\nPostcondition: (x:int) := x > 0.",
        expected="skip",
        note="P => Q holds outright; the only correct move is the skip law.",
        refinable=True,
    ),
    dict(
        id="A2-assign",
        tier="A",
        title="Direct assignment",
        spec="Precondition: (N:int) := N >= 0.\nPostcondition: (N:int) := x = N + 1.",
        expected="assignment x := N + 1",
        note="One assignment discharges the obligation P => Q[x:=E].",
        refinable=True,
    ),
    dict(
        id="A3-assign-guarded",
        tier="A",
        title="Assignment under a precondition",
        spec="Precondition: (A:int)(B:int) := A > B.\nPostcondition: (A:int)(B:int) := m = A /\ m > B.",
        expected="assignment m := A",
        note="Requires using the precondition A > B to discharge m > B.",
        refinable=True,
    ),
    dict(
        id="A4-impossible",
        tier="A",
        title="Unsatisfiable postcondition (negative control)",
        spec="Precondition: (A:int) := A > 0.\nPostcondition: (A:int) := y = A /\ y < 0.",
        expected="no refinement exists",
        note="Negative control: measures how much budget is burned before giving up.",
        refinable=False,
    ),

    # ---------------- Tier B: one structural decomposition ----------------
    dict(
        id="B1-sequential",
        tier="B",
        title="Two independent outputs (sequential composition)",
        spec="Precondition: (A:int)(B:int) := true.\nPostcondition: (A:int)(B:int) := s = A + B /\ d = A - B.",
        expected="sequential (R: s = A + B) ; s := A + B ; d := A - B",
        note="Needs sequential composition with a correctly chosen midpoint R.",
        refinable=True,
    ),
    dict(
        id="B2-max",
        tier="B",
        title="Maximum of two values (alternation)",
        spec="Precondition: (A:int)(B:int) := true.\nPostcondition: (A:int)(B:int) := (m = A \/ m = B) /\ m >= A /\ m >= B.",
        expected="alternation (G: A >= B) ; m := A / m := B",
        note="Canonical alternation case from the refinement-calculus literature.",
        refinable=True,
    ),
    dict(
        id="B3-abs",
        tier="B",
        title="Absolute value (alternation)",
        spec="Precondition: (A:int) := true.\nPostcondition: (A:int) := (y = A \/ y = -A) /\ y >= 0.",
        expected="alternation (G: A >= 0) ; y := A / y := -A",
        note="Alternation plus a negated expression in one branch.",
        refinable=True,
    ),

    # ---------------- Tier C: the paper's hard cases ----------------
    dict(
        id="C1-sqrt-loose",
        tier="C",
        title="Square root, loose postcondition (paper Fig. 3)",
        spec="Precondition: (N:float) := N >= 0.\nPostcondition: (N:float) := x * x <= N.",
        expected="assignment x := 0 (degenerate but valid)",
        note="Tests whether the model finds the cheap valid witness or over-reaches "
             "for sqrt(N), which L_spec cannot express.",
        refinable=True,
    ),
    dict(
        id="C2-sqrt-tight",
        tier="C",
        title="Square root, tight postcondition",
        spec="Precondition: (N:float) := N >= 1.\nPostcondition: (N:float) := x * x <= N /\ (x + 1) * (x + 1) > N.",
        expected="no closed-form assignment; needs sequential + iteration",
        note="Genuinely hard: nonlinear, and sqrt is not in the L_spec term language.",
        refinable=True,
    ),
    dict(
        id="C3-loop-pinned",
        tier="C",
        title="Counting loop with the initialisation pinned into the invariant",
        spec="Precondition: (N:int)(i:int) := N >= 0 /\ i = 0.\nPostcondition: (N:int)(i:int) := i >= N.",
        expected="iteration (G: i < N, V: N - i)",
        note="The engine reuses the precondition as the loop invariant, so i = 0 is "
             "pinned and no body can preserve it. Probes that limitation.",
        refinable=True,
    ),
    dict(
        id="C4-loop-invariant",
        tier="C",
        title="Counting loop with a proper invariant",
        spec="Precondition: (N:int)(i:int) := i <= N.\nPostcondition: (N:int)(i:int) := i = N.",
        expected="iteration (G: i < N, V: N - i) ; body i := i + 1",
        note="Precondition is already a usable invariant; the well-formed loop case.",
        refinable=True,
    ),
]

CASES_BY_ID = {c["id"]: c for c in CASES}
