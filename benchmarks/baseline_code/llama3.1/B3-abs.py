# model:  llama3.1:latest (think=None)
# case:   B3-abs -- Absolute value (alternation)
# spec:   Precondition: (A:int) := true.
#         Postcondition: (A:int) := (y = A \/ y = -A) /\ y >= 0.
# intent: Given an integer A, return y, the absolute value of A.

def f(A: int) -> int:
    if A >= 0:
        return A
    else:
        return -A