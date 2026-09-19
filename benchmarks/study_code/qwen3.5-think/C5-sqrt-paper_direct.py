# arm:    direct (model wrote this code itself; nothing verified it)
# model:  qwen3.5:latest
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

import math
                x = math.sqrt(N)
                # Ensure x*x <= N
                if x * x > N:
                    # Reduce x slightly
                    # How much? Just enough.
                    # But we don't know the exact error bound.
                    # A safe bet is to use a binary search or simply subtract a small epsilon.
                    # But subtracting arbitrary epsilon might violate (x+e)^2 > N if e is tiny.