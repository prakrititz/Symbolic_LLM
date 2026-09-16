# model:  llama3.1:latest (think=None)
# case:   C3-loop-pinned -- Counting loop with the initialisation pinned into the invariant
# spec:   Precondition: (N:int)(i:int) := N >= 0 /\ i = 0.
#         Postcondition: (N:int)(i:int) := i >= N.
# intent: Given a non-negative integer N, starting from i = 0, return a value i that is greater than or equal to N.

def f(N: int) -> int:
    i = 0
    while i < N:
        i += 1
    return i