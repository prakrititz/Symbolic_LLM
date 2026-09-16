# model:  qwen3.5:latest (think=False)
# case:   B1-sequential -- Two independent outputs (sequential composition)
# spec:   Precondition: (A:int)(B:int) := true.
#         Postcondition: (A:int)(B:int) := s = A + B /\ d = A - B.
# intent: Given integers A and B, return the pair (s, d) where s is A + B and d is A - B.

def f(A: int, B: int) -> tuple:
    return (A + B, A - B)