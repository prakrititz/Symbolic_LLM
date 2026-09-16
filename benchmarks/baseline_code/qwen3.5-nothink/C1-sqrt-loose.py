# model:  qwen3.5:latest (think=False)
# case:   C1-sqrt-loose -- Square root, loose postcondition (paper Fig. 3)
# spec:   Precondition: (N:float) := N >= 0.
#         Postcondition: (N:float) := x * x <= N.
# intent: Given a non-negative number N, return a number x whose square is at most N.

def f(N: float) -> float:
    return N ** 0.5