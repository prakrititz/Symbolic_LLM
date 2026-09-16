"""The refiner must reject refinement steps that make no progress.

strengthen_post with R = Q, and weaken_pre with R = P, discharge their proof
obligations trivially (Q => Q, P => P) and regenerate the parent specification
verbatim. Without a progress guard the search recurses into an identical node
forever, which is what exhausted the call budget on otherwise trivial cases.
"""
import json

import pytest

from FormalLLM.agent.refiner import AutomatedRefiner, RefinementExhausted
from FormalLLM.llm.provider import MockProvider
from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import AttemptStatus

SPEC = """
Precondition: (x:int) := x > 5.
Postcondition: (x:int) := x > 0.
"""


def _run(responses, max_retries=4):
    graph = RefinementGraph(parse_spec(SPEC))
    llm = MockProvider(responses)
    refiner = AutomatedRefiner(RefinementEngine(), llm, max_retries=max_retries)
    return graph, llm, refiner


def test_strengthen_post_identity_is_rejected():
    """R = Q reproduces the parent spec and must not be accepted."""
    responses = [json.dumps({"law": "strengthen_post",
                             "parameters": {"intermediate_post": "x > 0"}})] * 4
    graph, _, refiner = _run(responses)

    with pytest.raises(RefinementExhausted):
        refiner.refine_node(graph, graph.root_id)

    assert all(a.status == AttemptStatus.REJECTED for a in graph.attempts.values())
    # The no-op must not have spawned a descendant chain.
    assert len(graph.nodes) == 1


def test_weaken_pre_identity_is_rejected():
    """R = P reproduces the parent spec and must not be accepted."""
    responses = [json.dumps({"law": "weaken_pre",
                             "parameters": {"intermediate_pre": "x > 5"}})] * 4
    graph, _, refiner = _run(responses)

    with pytest.raises(RefinementExhausted):
        refiner.refine_node(graph, graph.root_id)

    assert all(a.status == AttemptStatus.REJECTED for a in graph.attempts.values())
    assert len(graph.nodes) == 1


def test_progress_guard_does_not_block_real_refinement():
    """A strengthen_post that genuinely strengthens Q is still accepted."""
    responses = [
        json.dumps({"law": "strengthen_post",
                    "parameters": {"intermediate_post": "x > 3"}}),
        json.dumps({"law": "skip", "parameters": {}}),
    ]
    graph, _, refiner = _run(responses)

    assert refiner.refine_node(graph, graph.root_id) is True
    assert graph.is_complete(graph.root_id)
    laws = [a.law for a in graph.attempts.values()
            if a.status == AttemptStatus.ACCEPTED]
    assert laws == ["strengthen_post", "skip"]


def test_guard_catches_non_adjacent_ancestor_repeat():
    """A spec repeating a grandparent, not just the parent, is also a no-op."""
    responses = [
        json.dumps({"law": "strengthen_post",
                    "parameters": {"intermediate_post": "x > 3"}}),
        # back to the original postcondition: the root spec reappears
        json.dumps({"law": "strengthen_post",
                    "parameters": {"intermediate_post": "x > 0"}}),
    ] * 4
    graph, _, refiner = _run(responses, max_retries=2)

    try:
        refiner.refine_node(graph, graph.root_id)
    except RefinementExhausted:
        pass

    keys = [(n.specification.precondition.expr, n.specification.postcondition.expr)
            for n in graph.nodes.values()]
    assert len(keys) == len(set(map(str, keys))), "a specification was duplicated in the graph"
