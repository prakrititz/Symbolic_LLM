# arm:    direct (model wrote this code itself; nothing verified it)
# model:  ornith:9b
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    lo, hi = 0.0, N + 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if mid * mid <= N:
            lo = mid
        else:
            hi = mid
    return lo