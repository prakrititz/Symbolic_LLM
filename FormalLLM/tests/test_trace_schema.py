"""The exported trace must be complete enough to replay and mine.

M6's law-learning algorithm reads a corpus of these traces. A field missing
from the export is not recoverable later, so these tests pin what a trace
carries rather than only that it serialises.
"""

import json

import pytest

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.llm.parser import parse_expr
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import AttemptStatus, NodeStatus
from FormalLLM.trace.serializer import (
    TRACE_SCHEMA_VERSION, graph_to_dict, export_graph_json, export_graph_text,
    validate_trace,
)


def build_refined_graph():
    """A two-step refinement: sequential split, then an assignment on part 1."""
    spec = parse_spec("Precondition: (N:int) := N >= 0.\n"
                      "Postcondition: (N:int) := x = N + 1.")
    graph = RefinementGraph(spec)
    engine = RefinementEngine()

    result = engine.apply(spec, "sequential", {"intermediate": parse_expr("N >= 0")})
    attempt_id = graph.record_attempt(graph.root_id, "sequential",
                                      {"intermediate": parse_expr("N >= 0")})
    roles = {role: graph.create_node(sub) for role, sub in result.by_role().items()}
    graph.attempts[attempt_id].destination_roles = roles
    graph.attempts[attempt_id].update_status(AttemptStatus.ACCEPTED)
    graph.nodes[graph.root_id].status = NodeStatus.DELEGATED

    part2 = roles["part2"]
    params = {"variable": "x", "expr": parse_expr("N + 1")}
    sub_result = engine.apply(graph.nodes[part2].specification, "assignment", params)
    sub_attempt = graph.record_attempt(part2, "assignment", params)
    graph.attempts[sub_attempt].update_status(AttemptStatus.ACCEPTED)
    graph.nodes[part2].status = NodeStatus.REFINED
    graph.nodes[part2].program = sub_result.program

    return graph, roles


def test_trace_is_valid_and_versioned():
    graph, _ = build_refined_graph()
    data = graph_to_dict(graph)

    assert data["schema_version"] == TRACE_SCHEMA_VERSION
    validate_trace(data)


def test_trace_survives_a_json_round_trip():
    graph, _ = build_refined_graph()
    restored = json.loads(export_graph_json(graph))

    validate_trace(restored)
    assert restored == graph_to_dict(graph)


def test_trace_records_law_parameters():
    """Regression: parameters were dropped, so two steps of the same law were
    indistinguishable in the record and no trace could be replayed."""
    graph, _ = build_refined_graph()
    attempts = graph_to_dict(graph)["attempts"]

    sequential = next(a for a in attempts.values() if a["law"] == "sequential")
    assert sequential["parameters"]["intermediate"] == "(N >= 0)"

    assignment = next(a for a in attempts.values() if a["law"] == "assignment")
    assert assignment["parameters"] == {"variable": "x", "expr": "(N + 1)"}


def test_recorded_expression_parameters_parse_back():
    """Stored parameters are L_spec source, so a trace can be replayed."""
    graph, _ = build_refined_graph()
    attempts = graph_to_dict(graph)["attempts"]
    assignment = next(a for a in attempts.values() if a["law"] == "assignment")

    assert parse_expr(assignment["parameters"]["expr"]) is not None


def test_trace_records_the_generated_program():
    graph, roles = build_refined_graph()
    nodes = graph_to_dict(graph)["nodes"]

    assert nodes[roles["part2"]]["program"] == "x := (N + 1)"
    assert nodes[roles["part1"]]["program"] is None


def test_validate_rejects_a_dangling_destination():
    graph, _ = build_refined_graph()
    data = graph_to_dict(graph)
    attempt = next(a for a in data["attempts"].values() if a["destination_roles"])
    attempt["destination_roles"]["part1"] = "N99"

    with pytest.raises(ValueError, match="not a node"):
        validate_trace(data)


def test_validate_rejects_an_unreadable_version():
    graph, _ = build_refined_graph()
    data = graph_to_dict(graph)
    data["schema_version"] = TRACE_SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="schema_version"):
        validate_trace(data)


def test_text_export_shows_parameters():
    graph, _ = build_refined_graph()
    text = export_graph_text(graph)

    assert "Parameters:" in text
    assert "variable=x" in text
