# model:  llama3.1:latest (think=None)
# case:   A3-assign-guarded -- Assignment under a precondition
# spec:   Precondition: (A:int)(B:int) := A > B.
#         Postcondition: (A:int)(B:int) := m = A /\ m > B.
# intent: Given integers A and B with A > B, return a value m such that m equals A and m is greater than B.

def f(A: int, B: int) -> int:
    if A > B:
        return A
    else:
        raise ValueError("A must be greater than B")