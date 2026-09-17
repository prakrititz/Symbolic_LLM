# arm:    direct (model wrote this code itself; nothing verified it)
# model:  qwen3.5:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    if N < 0 or e <= 0:
        raise ValueError("Precondition violated: N must be >= 0 and e must be > 0")
    
    x = N ** 0.5
    
    while True:
        lower_bound = x - e
        upper_bound = x + e
        
        if x * x <= N and N < (x + e) * (x + e):
            return x
        
        if x * x > N:
            x -= e / 2
        else:
            x += e / 2