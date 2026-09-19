# arm:    direct (model wrote this code itself; nothing verified it)
# model:  gpt-oss:120b
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    if N < 0 or e <= 0:
        raise ValueError("N must be >= 0 and e must be > 0")
    low = 0.0
    high = max(1.0, N) + e
    for _ in range(200):
        mid = (low + high) * 0.5
        if mid * mid <= N < (mid + e) * (mid + e):
            return mid
        if mid * mid > N:
            high = mid
        else:
            low = mid
    return low