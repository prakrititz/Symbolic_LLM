# arm:    direct_nostdlib (model wrote this code itself; nothing verified it)
# model:  qwen3.5:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    x = N
    if x > 0:
        while True:
            next_x = (x + N / x) / 2
            if abs(next_x - x) <= e:
                return next_x
            x = next_x
    else:
        return 0.0