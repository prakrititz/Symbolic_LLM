# arm:    direct (model wrote this code itself; nothing verified it)
# model:  llama3.1:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

import math

def f(N: float, e: float) -> float:
    if N < 0 or e <= 0:
        raise ValueError("N must be non-negative and e must be positive")
    low = math.ceil(math.sqrt(N)) - 1
    high = math.floor(math.sqrt(N)) + 1
    while high - low > 1:
        mid = (low + high) / 2
        if mid * mid <= N and N < (mid + e) * (mid + e):
            return mid
        elif mid * mid <= N:
            low = mid
        else:
            high = mid
    return low if low * low <= N else high