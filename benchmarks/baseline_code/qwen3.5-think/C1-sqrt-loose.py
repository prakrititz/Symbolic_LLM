# model:  qwen3.5:latest (think=True)
# case:   C1-sqrt-loose -- Square root, loose postcondition (paper Fig. 3)
# spec:   Precondition: (N:float) := N >= 0.
#         Postcondition: (N:float) := x * x <= N.
# intent: Given a non-negative number N, return a number x whose square is at most N.

import math
        N = 3.0
        x = math.sqrt(N)
        print(x*x <= N) # True usually?