# model:  llama3.1:latest (think=None)
# case:   C2-sqrt-tight -- Square root, tight postcondition
# spec:   Precondition: (N:float) := N >= 1.
#         Postcondition: (N:float) := x * x <= N /\ (x + 1) * (x + 1) > N.
# intent: Given a number N >= 1, return the integer square root x: the largest integer whose square is at most N. So x*x <= N < (x+1)*(x+1).

def f(N: float) -> int:
    if N < 1:
        raise ValueError("Input must be a positive number")
    x = int(N ** 0.5)
    while (x + 1) * (x + 1) <= N:
        x += 1
    return x