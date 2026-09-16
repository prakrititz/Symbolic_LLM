# model:  llama3.1:latest (think=None)
# case:   C4-loop-invariant -- Counting loop with a proper invariant
# spec:   Precondition: (N:int)(i:int) := i <= N.
#         Postcondition: (N:int)(i:int) := i = N.
# intent: Given integers i and N with i <= N, count i up until it equals N, and return i.

def f(i: int, N: int) -> int:
    while i < N:
        i += 1
    return i