# model:  ornith:9b (think=None)
# case:   C1-sqrt-loose -- Square root, loose postcondition (paper Fig. 3)
# spec:   Precondition: (N:float) := N >= 0.
#         Postcondition: (N:float) := x * x <= N.
# intent: Given a non-negative number N, return a number x whose square is at most N.

import math

def f(N: float) -> float:
    return math.sqrt(N)