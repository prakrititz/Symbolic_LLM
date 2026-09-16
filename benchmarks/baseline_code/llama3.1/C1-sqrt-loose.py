# model:  llama3.1:latest (think=None)
# case:   C1-sqrt-loose -- Square root, loose postcondition (paper Fig. 3)
# spec:   Precondition: (N:float) := N >= 0.
#         Postcondition: (N:float) := x * x <= N.
# intent: Given a non-negative number N, return a number x whose square is at most N.

def f(N: float) -> float:
    """
    Given a non-negative number N, return a number x whose square is at most N.
    
    :param N: A non-negative float
    :return: A float whose square is at most N
    """
    if N < 0:
        raise ValueError("Input must be a non-negative number")
    return N ** 0.5