"""Engine regression tests: a known-good refinement must still verify.

These replay refinements written *by hand*. They are not a measurement of
anything: they say only that if someone supplies the right law, invariant,
guard and variant, the engine accepts them and Z3 discharges every obligation.

That distinction was lost when the same scripted moves were run as an "oracle"
configuration of the benchmark and reported next to model results as though
"oracle: 10/12" were a score. It is not -- the playbook was written by the same
person reading the results, and every entry was added for the case it solves.
The value of these scripts is as regression tests, which is what they are here:
if a change to a law or to the frame handling breaks a refinement that used to
verify, one of these fails.

Nothing in this file may be quoted as a result.
"""

import pytest

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.llm.parser import parse_expr
from FormalLLM.refinement.engine import RefinementEngine, VerificationError
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import AttemptStatus, NodeStatus
from FormalLLM.lpl.to_python import to_python


def apply_step(graph, engine, node_id, law, params):
    """Apply one hand-written step, asserting the engine accepts it."""
    result = engine.apply(graph.nodes[node_id].specification, law, params)
    attempt = graph.attempts[graph.record_attempt(node_id, law, params)]
    attempt.update_status(AttemptStatus.ACCEPTED)
    if result.program is not None:
        graph.nodes[node_id].program = result.program
        graph.nodes[node_id].status = NodeStatus.REFINED
        return {}
    roles = {r: graph.create_node(s) for r, s in result.by_role().items()}
    attempt.destination_roles = roles
    graph.nodes[node_id].status = NodeStatus.DELEGATED
    return roles


def expr_params(**kwargs):
    return {k: (v if not isinstance(v, str) else parse_expr(v))
            for k, v in kwargs.items()}


def test_sqrt_with_error_bound_is_reachable():
    """The paper's motivating example (Figures 2-3) still verifies."""
    spec = parse_spec(
        "Frame: x.\n"
        "Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0.\n"
        "Postcondition: (N:float)(e:float) := x*x <= N /\\ N < (x+e)*(x+e)."
    )
    engine, graph = RefinementEngine(), RefinementGraph(spec)

    roles = apply_step(graph, engine, graph.root_id, "iteration", expr_params(
        invariant="(x * x) <= N && x >= 0",
        guard="N >= (x + e) * (x + e)",
        variant="N - (x * x)"))
    apply_step(graph, engine, roles["init"], "assignment",
               {"variable": "x", "expr": parse_expr("0")})
    apply_step(graph, engine, roles["body"], "assignment",
               {"variable": "x", "expr": parse_expr("x + e")})

    assert graph.is_complete(graph.root_id)
    assert to_python(graph.reconstruct_program()).split("\n")[0] == "x = 0"


def test_counting_loop_with_supplied_invariant_is_reachable():
    """C3: the precondition pins `i = 0`, so the invariant must be supplied.

    This is the case whose benchmark note used to read "the engine reuses the
    precondition as the loop invariant, so i = 0 is pinned and no body can
    preserve it". That was a defect in the iteration law, not a property of the
    problem, and this test is what stops it coming back.
    """
    spec = parse_spec(
        "Frame: i:int.\n"
        "Precondition: (N:int)(i:int) := N >= 0 /\\ i = 0.\n"
        "Postcondition: (N:int)(i:int) := i >= N."
    )
    engine, graph = RefinementEngine(), RefinementGraph(spec)

    roles = apply_step(graph, engine, graph.root_id, "iteration",
                       expr_params(invariant="i <= N", guard="i < N", variant="N - i"))
    apply_step(graph, engine, roles["init"], "skip", {})
    apply_step(graph, engine, roles["body"], "assignment",
               {"variable": "i", "expr": parse_expr("i + 1")})

    assert graph.is_complete(graph.root_id)


def test_integer_division_is_reachable():
    """D1: Morgan's quotient/remainder loop, the paper's Table 7 family."""
    spec = parse_spec(
        "Frame: q:int, r:int.\n"
        "Precondition: (n:int)(d:int) := n >= 0 /\\ d > 0.\n"
        "Postcondition: (n:int)(d:int) := q*d + r = n /\\ r >= 0 /\\ r < d."
    )
    engine, graph = RefinementEngine(), RefinementGraph(spec)

    roles = apply_step(graph, engine, graph.root_id, "iteration", expr_params(
        invariant="q*d + r = n && r >= 0", guard="r >= d", variant="r"))

    init = apply_step(graph, engine, roles["init"], "sequential",
                      expr_params(intermediate="q = 0"))
    apply_step(graph, engine, init["part1"], "assignment",
               {"variable": "q", "expr": parse_expr("0")})
    apply_step(graph, engine, init["part2"], "assignment",
               {"variable": "r", "expr": parse_expr("n")})

    body = apply_step(graph, engine, roles["body"], "sequential",
                      expr_params(intermediate="(q+1)*d + r = n && r >= 0 && r < r0"))
    apply_step(graph, engine, body["part1"], "assignment",
               {"variable": "r", "expr": parse_expr("r - d")})
    apply_step(graph, engine, body["part2"], "assignment",
               {"variable": "q", "expr": parse_expr("q + 1")})

    assert graph.is_complete(graph.root_id)


def test_iteration_without_a_variant_is_rejected_clearly():
    """Omitting the variant must say so, not silently default to a constant."""
    spec = parse_spec(
        "Frame: x.\n"
        "Precondition: (N:float)(e:float) := N >= 0 /\\ e > 0.\n"
        "Postcondition: (N:float)(e:float) := x*x <= N /\\ N < (x+e)*(x+e)."
    )
    with pytest.raises(ValueError, match="variant"):
        RefinementEngine().apply(spec, "iteration", {
            "guard": parse_expr("N >= (x + e) * (x + e)"),
            "invariant": parse_expr("(x * x) <= N")})
