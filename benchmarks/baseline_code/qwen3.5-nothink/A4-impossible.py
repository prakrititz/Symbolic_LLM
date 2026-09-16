# model:  qwen3.5:latest (think=False)
# case:   A4-impossible -- Unsatisfiable postcondition (negative control)
# spec:   Precondition: (A:int) := A > 0.
#         Postcondition: (A:int) := y = A /\ y < 0.
# intent: Given a positive integer A, return a value y such that y equals A and y is less than 0.

def f(A: int) -> int:
    raise ValueError("No solution exists for A > 0 such that y = A and y < 0")