# model:  qwen3.5:latest (think=False)
# case:   B2-max -- Maximum of two values (alternation)
# spec:   Precondition: (A:int)(B:int) := true.
#         Postcondition: (A:int)(B:int) := (m = A \/ m = B) /\ m >= A /\ m >= B.
# intent: Given integers A and B, return m, the larger of the two.

def f(A: int, B: int) -> int:
    return A if A > B else B