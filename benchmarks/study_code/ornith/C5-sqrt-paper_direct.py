# arm:    direct (model wrote this code itself; nothing verified it)
# model:  ornith:9b
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

import math

def f(N: float, e: float) -> float:
    if N <= 0:
        return 0.0
    x = math.sqrt(N)
    if x * x > N:
        x = math.sqrt(N - 1e-300)  # tiny adjustment
    return x