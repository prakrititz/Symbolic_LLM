# arm:    direct (model wrote this code itself; nothing verified it)
# model:  llama3.1:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

def f(N: float, e: float) -> float:
    """
    Returns the square root of N to within e.
    
    :param N: A non-negative number.
    :param e: A positive error bound.
    :return: The square root of N to within e.
    """
    if N < 0 or e <= 0:
        raise ValueError("N must be non-negative and e must be positive")
    
    low = 0
    high = N
    
    while high - low > e:
        mid = (low + high) / 2
        if mid * mid <= N:
            low = mid
        else:
            high = mid
    
    return low