# arm:    direct (model wrote this code itself; nothing verified it)
# model:  qwen3-coder-next:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    if N == 0:
        return 0.0
    
    # Binary search for x in [0, max(1, N)]
    low = 0.0
    high = max(1.0, N)
    
    while True:
        mid = (low + high) / 2
        
        if mid * mid <= N:
            if N < (mid + e) * (mid + e):
                return mid
            low = mid
        else:
            high = mid