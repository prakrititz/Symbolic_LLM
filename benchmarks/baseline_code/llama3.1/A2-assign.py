# model:  llama3.1:latest (think=None)
# case:   A2-assign -- Direct assignment
# spec:   Precondition: (N:int) := N >= 0.
#         Postcondition: (N:int) := x = N + 1.
# intent: Given a non-negative integer N, return N + 1.

def f(N: int) -> int:
    """
    Given a non-negative integer N, return N + 1.
    
    Parameters:
    N (int): A non-negative integer.
    
    Returns:
    int: N + 1.
    """
    if N >= 0:
        return N + 1
    else:
        raise ValueError("Input must be a non-negative integer.")