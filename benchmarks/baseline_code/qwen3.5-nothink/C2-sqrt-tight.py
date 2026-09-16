# model:  qwen3.5:latest (think=False)
# case:   C2-sqrt-tight -- Square root, tight postcondition
# spec:   Precondition: (N:float) := N >= 1.
#         Postcondition: (N:float) := x * x <= N /\ (x + 1) * (x + 1) > N.
# intent: Given a number N >= 1, return the integer square root x: the largest integer whose square is at most N. So x*x <= N < (x+1)*(x+1).

def f(N: float) -> int:
    if N < 1:
        raise ValueError("N must be >= 1")
    x = int(N ** 0.5)
    return x