# arm:    direct (model wrote this code itself; nothing verified it)
# model:  ornith:9b
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# intent: Given a number N >= 0 and an error bound e > 0, return a number x such that x*x <= N and N < (x+e)*(x+e). In other words x is the square root of N to within e.

The user wants me to implement a Python function that computes an approximate square root of N within error bound e. The specification says:

- Precondition: N >= 0, e > 0
- Postcondition: x*x <= N and N < (x+e)*(x+e)

This means x is a lower bound on sqrt(N) such that the error is at most e.

I need to find x such that x <= sqrt(N) <= x + e.

A simple approach: use Newton's method or binary search. Let me think about what satisfies the postcondition.

If I use Newton's method starting from a reasonable initial guess, I can get a good approximation. But I need to ensure x*x <= N (i.e., x is not an overestimate).

Actually, let me think more carefully. The postcondition requires x*x <= N AND N < (x+e)*(x+e). So x must be a lower bound on sqrt(N), and the gap between x and sqrt(N) must be less than e.

One approach: binary search for sqrt(N). Start with low=0, high=max(1, N) (or some upper bound). Find the largest x such that x*x <= N. Then check if N < (x+e)*(x+e).

Actually, binary search for the largest x with x*x <= N would give us the floor of sqrt(N). But that might not satisfy N < (x+e)*(x+e) if e is very small.

Wait, if x is the largest number with x*x <= N, then (x+1)^2 > N. So N < (x+1)^2. If e >= 1, then N < (x+e)^2 is automatically satisfied. But if e < 1, we need to be more careful.

Actually, let me reconsider. If I binary search for the largest x with x*x <= N, then x is floor(sqrt(N)). Then (x+1)^2 > N, so N < (x+1)^2. If e >= 1, then (x+e)^2 >= (x+1)^2 > N, so the postcondition holds.

But if e < 1, then (x+e)^2 might not be > N. For example, if N=10, e=0.1, then sqrt(10)≈3.16, so x=3 (largest with x*x<=10). Then (x+e)^2 = 3.1^2 = 9.61 < 10. So the postcondition fails!

So binary search for the largest x with x*x <= N doesn't always work.

Let me think differently. I need x such that x*x <= N < (x+e)^2. This means x <= sqrt(N) < x+e, i.e., sqrt(N)-e < x <= sqrt(N).

So x can be any value in (sqrt(N)-e, sqrt(N)]. I should pick x = sqrt(N) - e/2 or something, but I need to compute it.

Actually, the simplest approach: use Newton's method to find sqrt(N), then clamp it to be <= sqrt(N). But floating point sqrt might give a value slightly above or below.

Let me use a different approach. Binary search for x in [0, N+1] such that x*x <= N. But I need to ensure the postcondition.

Actually, let me just use Python's math.sqrt and then adjust. But the spec says only standard library, and math is standard.

Wait, let me re-read: "Use only the Python standard library." So math module is fine.

Let me try: x = math.sqrt(N). Then if x*x > N (due to floating point), decrease x slightly. If x*x <= N, check if N < (x+e)^2.

Actually, the simplest correct approach: binary search.

Let me think about binary search more carefully.

I want to find x such that x*x <= N and N < (x+e)^2.

This is equivalent to: find x such that x <= sqrt(N) and x > sqrt(N) - e.

So I can