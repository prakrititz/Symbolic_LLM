# arm:    direct_nostdlib (model wrote this code itself; nothing verified it)
# model:  llama3.1:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    x = 0.0
    while True:
        if x*x <= N and N < (x+e)*(x+e):
            return x
        if x*x >= N:
            return N / x
        x += 1.0