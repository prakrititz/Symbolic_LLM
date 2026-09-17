# arm:    direct_nostdlib (model wrote this code itself; nothing verified it)
# model:  llama3.1:latest
# case:   D1-intdiv -- Integer division: quotient and remainder
# intent: Given integers n >= 0 and d > 0, return the pair (q, r) where q is the quotient and r the remainder of dividing n by d: q*d + r == n and 0 <= r < d.

def f(n: int, d: int) -> tuple:
    q = 0
    r = n
    while d <= r:
        r = r - d
        q = q + 1
    if r < 0:
        q = q - 1
        r = r + d
    return q, r