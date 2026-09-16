# model:  qwen3.5:latest (think=True)
# case:   C2-sqrt-tight -- Square root, tight postcondition
# spec:   Precondition: (N:float) := N >= 1.
#         Postcondition: (N:float) := x * x <= N /\ (x + 1) * (x + 1) > N.
# intent: Given a number N >= 1, return the integer square root x: the largest integer whose square is at most N. So x*x <= N < (x+1)*(x+1).

import math

    def f(N: float) -> int:
        return int(math.sqrt(N))