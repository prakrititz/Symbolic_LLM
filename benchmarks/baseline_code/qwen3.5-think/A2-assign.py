# model:  qwen3.5:latest (think=True)
# case:   A2-assign -- Direct assignment
# spec:   Precondition: (N:int) := N >= 0.
#         Postcondition: (N:int) := x = N + 1.
# intent: Given a non-negative integer N, return N + 1.

def f(N: int) -> int:
    return N + 1