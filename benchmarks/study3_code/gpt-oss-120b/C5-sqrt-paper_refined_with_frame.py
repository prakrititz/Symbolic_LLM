# arm: refinement, using gpt-oss-120b's OWN guard and variant, and its
# invariant plus the frame context the engine does not yet propagate.

def f(N: float, e: float) -> float:
    x = 0
    while (N >= ((x + e) * (x + e))):
        x = (x + e)
    return x
