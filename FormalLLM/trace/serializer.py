import json
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import NodeStatus, AttemptStatus
from FormalLLM.llm.prompts import to_string

def export_graph_json(graph: RefinementGraph) -> str:
    data = {
        "root_id": graph.root_id,
        "nodes": {},
        "attempts": {}
    }
    for n_id, node in graph.nodes.items():
        data["nodes"][n_id] = {
            "id": n_id,
            "specification": to_string(node.specification),
            "status": node.status.value,
            "attempts": node.attempts
        }
    for a_id, attempt in graph.attempts.items():
        data["attempts"][a_id] = {
            "id": a_id,
            "source_node_id": attempt.source_node_id,
            "law": attempt.law,
            "status": attempt.status.value,
            "status_history": [s.value for s in attempt.status_history],
            "destination_roles": attempt.destination_roles,
            "error_message": attempt.error_message,
            "counterexample": attempt.counterexample
        }
    return json.dumps(data, indent=2)

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
        out.append("")
        for a_id in node.attempts:
            attempt = graph.attempts[a_id]
            out.append("-" * 60)
            out.append(f"ATTEMPT {a_id} ({attempt.status.value.upper()})")
            out.append("-" * 60)
            out.append(f"Law: {attempt.law}")
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
