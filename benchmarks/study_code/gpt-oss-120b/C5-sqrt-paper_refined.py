# arm:    refinement (code EMITTED from the verified refinement tree)
# model:  gpt-oss:120b -- chose laws only, wrote no code
# case:   C5-sqrt-paper -- Square root within an error bound (the paper's motivating example)
# laws:   {'strengthen_post': 1, 'initialised_iteration': 1, 'assignment': 2}
# calls:  10 LLM calls, every step discharged by Z3

def f(N: float, e: float) -> float:
    x = 0
    while (((x + e) * (x + e)) <= N):
        x = (x + e)
    return x
