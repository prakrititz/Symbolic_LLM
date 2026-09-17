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
        spec="Frame: x.\nPrecondition: (x:int) := x > 5.\nPostcondition: (x:int) := x > 0.",
        expected="skip",
        note="P => Q holds outright; the only correct move is the skip law.",
        refinable=True,
    ),
    dict(
        id="A2-assign",
        tier="A",
        title="Direct assignment",
        spec="Frame: x.\nPrecondition: (N:int) := N >= 0.\nPostcondition: (N:int) := x = N + 1.",
        expected="assignment x := N + 1",
        note="One assignment discharges the obligation P => Q[x:=E].",
        refinable=True,
        test_cases=[
            {"inputs": {"N": 5}, "expected": {"x": 6}},
            {"inputs": {"N": 0}, "expected": {"x": 1}}
        ],
    ),
    dict(
        id="A3-assign-guarded",
        tier="A",
        title="Assignment under a precondition",
        spec="Frame: m.\nPrecondition: (A:int)(B:int) := A > B.\nPostcondition: (A:int)(B:int) := m = A /\ m > B.",
        expected="assignment m := A",
        note="Requires using the precondition A > B to discharge m > B.",
        refinable=True,
    ),
    dict(
        id="A4-impossible",
        tier="A",
        title="Unsatisfiable postcondition (negative control)",
        spec="Frame: y.\nPrecondition: (A:int) := A > 0.\nPostcondition: (A:int) := y = A /\ y < 0.",
        expected="no refinement exists",
        note="Negative control: measures how much budget is burned before giving up.",
        refinable=False,
    ),

    # ---------------- Tier B: one structural decomposition ----------------
    dict(
        id="B1-sequential",
        tier="B",
        title="Two independent outputs (sequential composition)",
        spec="Frame: s, d.\nPrecondition: (A:int)(B:int) := true.\nPostcondition: (A:int)(B:int) := s = A + B /\ d = A - B.",
        expected="sequential (R: s = A + B) ; s := A + B ; d := A - B",
        note="Needs sequential composition with a correctly chosen midpoint R.",
        refinable=True,
    ),
    dict(
        id="B2-max",
        tier="B",
        title="Maximum of two values (alternation)",
        spec="Frame: m.\nPrecondition: (A:int)(B:int) := true.\nPostcondition: (A:int)(B:int) := (m = A \/ m = B) /\ m >= A /\ m >= B.",
        expected="alternation (G: A >= B) ; m := A / m := B",
        note="Canonical alternation case from the refinement-calculus literature.",
        refinable=True,
    ),
    dict(
        id="B3-abs",
        tier="B",
        title="Absolute value (alternation)",
        spec="Frame: y.\nPrecondition: (A:int) := true.\nPostcondition: (A:int) := (y = A \/ y = -A) /\ y >= 0.",
        expected="alternation (G: A >= 0) ; y := A / y := -A",
        note="Alternation plus a negated expression in one branch.",
        refinable=True,
    ),

    # ---------------- Tier C: the paper's hard cases ----------------
    dict(
        id="C1-sqrt-loose",
        tier="C",
        title="Square root, loose postcondition (paper Fig. 3)",
        spec="Frame: x.\nPrecondition: (N:float) := N >= 0.\nPostcondition: (N:float) := x * x <= N.",
        expected="assignment x := 0 (degenerate but valid)",
        note="Tests whether the model finds the cheap valid witness or over-reaches "
             "for sqrt(N), which L_spec cannot express.",
        refinable=True,
        test_cases=[
            {"inputs": {"N": 16.0}, "expected": None},
            {"inputs": {"N": 0.0}, "expected": None},
            {"inputs": {"N": 42.5}, "expected": None}
        ],
    ),
    dict(
        id="C2-sqrt-tight",
        tier="C",
        title="Square root, tight postcondition",
        spec="Frame: x.\nPrecondition: (N:float) := N >= 1.\nPostcondition: (N:float) := x * x <= N /\ (x + 1) * (x + 1) > N.",
        expected="no closed-form assignment; needs sequential + iteration",
        note="Genuinely hard: nonlinear, and sqrt is not in the L_spec term language.",
        refinable=True,
    ),
    dict(
        id="C3-loop-pinned",
        tier="C",
        title="Counting loop with the initialisation pinned into the invariant",
        spec="Frame: i.\nPrecondition: (N:int)(i:int) := N >= 0 /\ i = 0.\nPostcondition: (N:int)(i:int) := i >= N.",
        expected="iteration (G: i < N, V: N - i)",
        note="The engine reuses the precondition as the loop invariant, so i = 0 is "
             "pinned and no body can preserve it. Probes that limitation.",
        refinable=True,
    ),
    dict(
        id="C5-sqrt-paper",
        tier="C",
        title="Square root within an error bound (the paper's motivating example)",
        spec="Frame: x.\nPrecondition: (N:float)(e:float) := N >= 0 /\\ e > 0.\n"
             "Postcondition: (N:float)(e:float) := x*x <= N /\\ N < (x+e)*(x+e).",
        expected="sequential (R: N>=0 /\\ e>0 /\\ x*x<=N /\\ x>=0) ; "
                 "x := 0 ; while N >= (x+e)*(x+e): x := x + e",
        note="Figure 1-3 of the paper. Copilot, GPT-4 and o1-preview all produce "
             "subtly wrong code here: a wrong upper bound for N < 1, a float "
             "fixed point that never terminates, and a bad initialisation for "
             "small N. `manual_sqrt.py` shows the engine can refine it, so a "
             "failure in the refinement arm is the model, not the calculus.",
        refinable=True,
    ),
    dict(
        id="C4-loop-invariant",
        tier="C",
        title="Counting loop with a proper invariant",
        spec="Frame: i.\nPrecondition: (N:int)(i:int) := i <= N.\nPostcondition: (N:int)(i:int) := i = N.",
        expected="iteration (G: i < N, V: N - i) ; body i := i + 1",
        note="Precondition is already a usable invariant; the well-formed loop case.",
        refinable=True,
    ),
    # ---------------- Tier D: CorC / Table 7 family ----------------
    dict(
        id="D1-intdiv",
        tier="D",
        title="Integer division: quotient and remainder",
        spec="Frame: q:int, r:int.\n"
             "Precondition: (n:int)(d:int) := n >= 0 /\\ d > 0.\n"
             "Postcondition: (n:int)(d:int) := q*d + r = n /\\ r >= 0 /\\ r < d.",
        expected="iteration (I: q*d+r=n && r>=0, G: r >= d, V: r) ; "
                 "q := 0 ; r := n ; while r >= d: r := r - d ; q := q + 1",
        note="Morgan's canonical loop example and the same family as the paper's "
             "Table 7 problems. Unlike the sqrt case there is no library "
             "shortcut for the direct arm, and unlike the array problems it is "
             "expressible in L_spec today. Verified refinable end to end.",
        refinable=True,
    ),
]

CASES_BY_ID = {c["id"]: c for c in CASES}
