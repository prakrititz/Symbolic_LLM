# arm:    direct (model wrote this code itself; nothing verified it)
# model:  gpt-oss:120b
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

import math

def f(N: float, e: float) -> float:
    if N < 0 or e <= 0:
        raise ValueError("Precondition violated")
    s = math.sqrt(N)
    x = s - e / 2.0
    return x if x > 0 else 0.0