# model:  qwen3.5:latest (think=False)
# case:   C3-loop-pinned -- Counting loop with the initialisation pinned into the invariant
# spec:   Precondition: (N:int)(i:int) := N >= 0 /\ i = 0.
#         Postcondition: (N:int)(i:int) := i >= N.
# intent: Given a non-negative integer N, starting from i = 0, return a value i that is greater than or equal to N.

def f(N: int) -> int:
    return N