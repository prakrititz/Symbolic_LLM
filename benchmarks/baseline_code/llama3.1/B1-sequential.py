# model:  llama3.1:latest (think=None)
# case:   B1-sequential -- Two independent outputs (sequential composition)
# spec:   Precondition: (A:int)(B:int) := true.
#         Postcondition: (A:int)(B:int) := s = A + B /\ d = A - B.
# intent: Given integers A and B, return the pair (s, d) where s is A + B and d is A - B.

def f(A: int, B: int) -> tuple:
    s = A + B
    d = A - B
    return s, d