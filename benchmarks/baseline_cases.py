"""Direct code-generation baseline: the same 11 specifications, but asking the
model for a Python function instead of driving it through the refinement engine.

This mirrors the paper's "NL"/"FS" baseline columns (Table 6), where the LLM is
given the specification and simply writes the program, with no refinement
calculus and no prover in the loop. Correctness is judged by executing the
generated function against generated inputs and checking the postcondition.

Each case supplies:
  nl        -- natural-language intent (the paper feeds NL alongside the spec)
  signature -- the exact function header the model must produce
  inputs    -- a list of argument tuples to test with
  check     -- check(args, result) -> bool, the postcondition
"""
import random

random.seed(20260916)


def _ints(n, lo=-50, hi=50):
    return [random.randint(lo, hi) for _ in range(n)]


BASELINE = {
    "A1-skip": dict(
        nl="Given an integer x that is already greater than 5, produce a value "
           "that is greater than 0.",
        signature="def f(x: int) -> int:",
        inputs=[(v,) for v in _ints(12, 6, 200)],
        check=lambda a, r: isinstance(r, int) and r > 0,
    ),
    "A2-assign": dict(
        nl="Given a non-negative integer N, return N + 1.",
        signature="def f(N: int) -> int:",
        inputs=[(v,) for v in _ints(12, 0, 200)],
        check=lambda a, r: r == a[0] + 1,
    ),
    "A3-assign-guarded": dict(
        nl="Given integers A and B with A > B, return a value m such that "
           "m equals A and m is greater than B.",
        signature="def f(A: int, B: int) -> int:",
        inputs=[(b + d, b) for b, d in zip(_ints(12), _ints(12, 1, 40))],
        check=lambda a, r: r == a[0] and r > a[1],
    ),
    "A4-impossible": dict(
        nl="Given a positive integer A, return a value y such that y equals A "
           "and y is less than 0.",
        signature="def f(A: int) -> int:",
        inputs=[(v,) for v in _ints(12, 1, 200)],
        check=lambda a, r: r == a[0] and r < 0,      # unsatisfiable by design
    ),
    "B1-sequential": dict(
        nl="Given integers A and B, return the pair (s, d) where s is A + B and "
           "d is A - B.",
        signature="def f(A: int, B: int) -> tuple:",
        inputs=list(zip(_ints(12), _ints(12))),
        check=lambda a, r: (isinstance(r, (tuple, list)) and len(r) == 2
                            and r[0] == a[0] + a[1] and r[1] == a[0] - a[1]),
    ),
    "B2-max": dict(
        nl="Given integers A and B, return m, the larger of the two.",
        signature="def f(A: int, B: int) -> int:",
        inputs=list(zip(_ints(12), _ints(12))),
        check=lambda a, r: r in (a[0], a[1]) and r >= a[0] and r >= a[1],
    ),
    "B3-abs": dict(
        nl="Given an integer A, return y, the absolute value of A.",
        signature="def f(A: int) -> int:",
        inputs=[(v,) for v in _ints(12)],
        check=lambda a, r: r in (a[0], -a[0]) and r >= 0,
    ),
    "C1-sqrt-loose": dict(
        nl="Given a non-negative number N, return a number x whose square is at "
           "most N.",
        signature="def f(N: float) -> float:",
        inputs=[(float(v),) for v in _ints(12, 0, 500)],
        check=lambda a, r: isinstance(r, (int, float)) and r * r <= a[0] + 1e-9,
    ),
    "C2-sqrt-tight": dict(
        nl="Given a number N >= 1, return the integer square root x: the largest "
           "integer whose square is at most N. So x*x <= N < (x+1)*(x+1).",
        signature="def f(N: float) -> int:",
        inputs=[(float(v),) for v in _ints(12, 1, 10_000)],
        check=lambda a, r: (isinstance(r, (int, float))
                            and r * r <= a[0] < (r + 1) * (r + 1)),
    ),
    "C3-loop-pinned": dict(
        nl="Given a non-negative integer N, starting from i = 0, return a value "
           "i that is greater than or equal to N.",
        signature="def f(N: int) -> int:",
        inputs=[(v,) for v in _ints(12, 0, 200)],
        check=lambda a, r: isinstance(r, int) and r >= a[0],
    ),
    "C5-sqrt-paper": dict(
        nl="Given a number N >= 0 and an error bound e > 0, return a number x "
           "such that x*x <= N and N < (x+e)*(x+e). In other words x is the "
           "square root of N to within e.",
        signature="def f(N: float, e: float) -> float:",
        # Chosen to cover the three failure modes the paper reports in Figure 1:
        # N < 1 (Copilot's upper bound is wrong), N = 5 (GPT-4 reaches a float
        # fixed point and loops forever), and N < (e/4)**2 (o1-preview starts x
        # negative). The remainder are ordinary values.
        inputs=[(0.5, 0.01), (0.25, 0.01), (0.9, 0.001),
                (5.0, 0.01), (5.0, 0.001),
                (1e-6, 0.01), (0.0, 0.01),
                (2.0, 0.01), (16.0, 0.01), (10000.0, 0.1),
                (1.0, 0.001), (123.456, 0.01)],
        check=lambda a, r: (isinstance(r, (int, float))
                            and r * r <= a[0] + 1e-9
                            and a[0] < (r + a[1]) * (r + a[1]) + 1e-9),
    ),
    "C4-loop-invariant": dict(
        nl="Given integers i and N with i <= N, count i up until it equals N, "
           "and return i.",
        signature="def f(i: int, N: int) -> int:",
        inputs=[(v, v + d) for v, d in zip(_ints(12), _ints(12, 0, 60))],
        check=lambda a, r: r == a[1],
    ),
    "D1-intdiv": dict(
        nl="Given integers n >= 0 and d > 0, return the pair (q, r) where q is "
           "the quotient and r the remainder of dividing n by d: q*d + r == n "
           "and 0 <= r < d.",
        signature="def f(n: int, d: int) -> tuple:",
        # Edge cases the paper's argument turns on: d = 1, d > n, n = 0, and
        # large ratios where a naive loop is slow but still correct.
        inputs=[(0, 1), (0, 7), (1, 1), (5, 1), (7, 3), (3, 7), (10, 10),
                (100, 7), (99, 100), (1, 1000), (12345, 11), (1000, 3)],
        check=lambda a, r: (isinstance(r, (tuple, list)) and len(r) == 2
                            and r[0] * a[1] + r[1] == a[0]
                            and 0 <= r[1] < a[1]),
    ),
}

# Cases whose postcondition no implementation can satisfy (negative control).
UNSATISFIABLE = {"A4-impossible"}
