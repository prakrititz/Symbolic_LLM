"""Serialisation of a refinement graph.

The exported trace is the input to the law-learning algorithm (paper §6.1),
which mines refinement *trees* for recurring law sequences and specification
patterns. That needs more than a picture of the search: it needs, for every
accepted step, which law ran, **with which parameters**, against which
specification, and what program came out.

The previous export recorded neither ``attempt.parameters`` nor
``node.program``, so a trace could not be replayed or mined -- two `iteration`
steps with different guards and variants were indistinguishable in the record.
Both are included here, and the payload carries a ``schema_version`` so a
stored corpus stays readable as the format grows.
"""

import json
from typing import Any, Dict

from FormalLLM.lspec.ast import ASTNode
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.llm.prompts import to_string

#: Bump on any change to the exported shape.
#:
#: 1 -- nodes/attempts with law, status history, roles, parameters and program.
TRACE_SCHEMA_VERSION = 1


def _render(value: Any) -> Any:
    """Render one law parameter for storage.

    Expression parameters are AST nodes; they are stored in their L_spec source
    form, which ``llm.parser.parse_expr`` reads back. Bare identifiers and
    other JSON-safe scalars are stored as they are.
    """
    if isinstance(value, ASTNode):
        return to_string(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def graph_to_dict(graph: RefinementGraph) -> Dict[str, Any]:
    """The whole graph as a JSON-safe dict."""
    data: Dict[str, Any] = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "root_id": graph.root_id,
        "nodes": {},
        "attempts": {},
    }

    for n_id, node in graph.nodes.items():
        data["nodes"][n_id] = {
            "id": n_id,
            "specification": to_string(node.specification),
            "status": node.status.value,
            "attempts": list(node.attempts),
            # Present only on a terminally refined node; this is the code the
            # law produced, and what makes a trace replayable.
            "program": to_string(node.program) if node.program is not None else None,
        }

    for a_id, attempt in graph.attempts.items():
        data["attempts"][a_id] = {
            "id": a_id,
            "source_node_id": attempt.source_node_id,
            "law": attempt.law,
            "parameters": {k: _render(v) for k, v in (attempt.parameters or {}).items()},
            "status": attempt.status.value,
            "status_history": [s.value for s in attempt.status_history],
            "destination_roles": dict(attempt.destination_roles),
            "error_message": attempt.error_message,
            "counterexample": attempt.counterexample,
        }

    return data


def export_graph_json(graph: RefinementGraph) -> str:
    return json.dumps(graph_to_dict(graph), indent=2)


def validate_trace(data: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``data`` is not a well-formed trace.

    Checks the structural invariants a consumer may rely on: the version is one
    this build understands, every referenced id resolves, and every node's
    inbound and outbound links agree with the attempts that name it.
    """
    version = data.get("schema_version")
    if version != TRACE_SCHEMA_VERSION:
        raise ValueError(
            f"trace schema_version {version!r} is not {TRACE_SCHEMA_VERSION}"
        )

    nodes, attempts = data.get("nodes", {}), data.get("attempts", {})

    if data.get("root_id") not in nodes:
        raise ValueError(f"root_id {data.get('root_id')!r} is not among the nodes")

    for a_id, attempt in attempts.items():
        if attempt["source_node_id"] not in nodes:
            raise ValueError(
                f"attempt {a_id} has source {attempt['source_node_id']!r}, which is not a node"
            )
        if a_id not in nodes[attempt["source_node_id"]]["attempts"]:
            raise ValueError(
                f"attempt {a_id} is not listed on its source node "
                f"{attempt['source_node_id']}"
            )
        for role, dst in attempt["destination_roles"].items():
            if dst not in nodes:
                raise ValueError(
                    f"attempt {a_id} role {role!r} points at {dst!r}, which is not a node"
                )

    for n_id, node in nodes.items():
        for a_id in node["attempts"]:
            if a_id not in attempts:
                raise ValueError(f"node {n_id} lists attempt {a_id!r}, which does not exist")
        if node["status"] not in {s.value for s in NodeStatus}:
            raise ValueError(f"node {n_id} has unknown status {node['status']!r}")

    for a_id, attempt in attempts.items():
        if attempt["status"] not in {s.value for s in AttemptStatus}:
            raise ValueError(f"attempt {a_id} has unknown status {attempt['status']!r}")


def export_graph_text(graph: RefinementGraph) -> str:
    # A simple pretty printer
    out = []
    for n_id in sorted(graph.nodes.keys()):
        node = graph.nodes[n_id]
        out.append("=" * 60)
        out.append(f"NODE {n_id} ({node.status.value.upper()})")
        out.append("=" * 60)
        out.append("Specification:")
        out.append(to_string(node.specification))
        if node.program is not None:
            out.append("Program:")
            out.append(to_string(node.program))
        out.append("")
        for a_id in node.attempts:
            attempt = graph.attempts[a_id]
            out.append("-" * 60)
            out.append(f"ATTEMPT {a_id} ({attempt.status.value.upper()})")
            out.append("-" * 60)
            out.append(f"Law: {attempt.law}")
            if attempt.parameters:
                rendered = ", ".join(
                    f"{k}={_render(v)}" for k, v in attempt.parameters.items()
                )
                out.append(f"Parameters: {rendered}")
            if attempt.counterexample:
                out.append("Counterexample:")
                out.append(attempt.counterexample)
            if attempt.error_message:
                out.append("Error:")
                out.append(attempt.error_message)
            if attempt.destination_roles:
                out.append("Destinations:")
                for role, dst in attempt.destination_roles.items():
                    out.append(f"  {role}: {dst}")
        out.append("")
    return "\n".join(out)
