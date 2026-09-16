# model:  ornith:9b (think=True)
# case:   A4-impossible -- Unsatisfiable postcondition (negative control)
# spec:   Precondition: (A:int) := A > 0.
#         Postcondition: (A:int) := y = A /\ y < 0.
# intent: Given a positive integer A, return a value y such that y equals A and y is less than 0.

def f(A: int) -> int:
    return A