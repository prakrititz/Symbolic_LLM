"""Instrumented runner for a single (config, case) refinement trial."""
import json
import time
import traceback
from typing import Any, Dict, List, Optional

from FormalLLM.lspec.parser import parse_spec
from FormalLLM.refinement.engine import RefinementEngine
from FormalLLM.refinement.graph.graph import RefinementGraph
from FormalLLM.refinement.graph.status import AttemptStatus, NodeStatus
from FormalLLM.agent.refiner import AutomatedRefiner, RefinementExhausted
from FormalLLM.llm.provider import LLMProvider, OllamaProvider
from FormalLLM.llm.prompts import to_string
from FormalLLM.lpl.to_python import to_python


class BudgetExhausted(Exception):
    """Raised to abort a trial once the LLM-call budget is spent."""


class InstrumentedProvider(LLMProvider):
    """Wraps a provider, recording every call and enforcing a call budget."""

    def __init__(self, inner: LLMProvider, budget: int):
        self.inner = inner
        self.budget = budget
        self.calls: List[Dict[str, Any]] = []

    def generate(self, prompt: str) -> str:
        if len(self.calls) >= self.budget:
            raise BudgetExhausted(f"LLM call budget of {self.budget} exhausted")
        t0 = time.time()
        error = None
        try:
            text = self.inner.generate(prompt)
        except Exception as e:          # network / ollama failure
            text = ""
            error = f"{type(e).__name__}: {e}"
        dt = time.time() - t0
        meta = getattr(self.inner, "last_meta", {}) or {}
        self.calls.append(dict(
            index=len(self.calls),
            latency_s=round(dt, 3),
            prompt_chars=len(prompt),
            response=text,
            transport_error=error,
            prompt_tokens=meta.get("prompt_eval_count"),
            output_tokens=meta.get("eval_count"),
            used_thinking_channel=meta.get("used_thinking_channel"),
        ))
        if error:
            raise Exception(error)
        return text


def program_to_str(node, indent: int = 0) -> str:
    from FormalLLM.lpl.ast import Assignment, Skip, SequentialComposition, IfElse, While
    pad = "  " * indent
    if node is None:
        return pad + "<none>"
    if isinstance(node, Skip):
        return pad + "pass"
    if isinstance(node, Assignment):
        return f"{pad}{node.variable} = {to_string(node.expr)}"
    if isinstance(node, SequentialComposition):
        return program_to_str(node.first, indent) + "\n" + program_to_str(node.second, indent)
    if isinstance(node, IfElse):
        return (f"{pad}if {to_string(node.guard)}:\n"
                f"{program_to_str(node.then_branch, indent + 1)}\n"
                f"{pad}else:\n"
                f"{program_to_str(node.else_branch, indent + 1)}")
    if isinstance(node, While):
        return (f"{pad}while {to_string(node.guard)}:\n"
                f"{program_to_str(node.body, indent + 1)}")
    return pad + str(node)


def summarise_graph(graph: RefinementGraph) -> Dict[str, Any]:
    attempt_status: Dict[str, int] = {}
    law_counts: Dict[str, int] = {}
    law_accepted: Dict[str, int] = {}
    errors: List[str] = []
    for a in graph.attempts.values():
        attempt_status[a.status.value] = attempt_status.get(a.status.value, 0) + 1
        law_counts[a.law] = law_counts.get(a.law, 0) + 1
        if a.status == AttemptStatus.ACCEPTED:
            law_accepted[a.law] = law_accepted.get(a.law, 0) + 1
        if a.error_message:
            errors.append(a.error_message)
    node_status: Dict[str, int] = {}
    for n in graph.nodes.values():
        node_status[n.status.value] = node_status.get(n.status.value, 0) + 1
    return dict(
        n_nodes=len(graph.nodes),
        n_attempts=len(graph.attempts),
        attempt_status=attempt_status,
        node_status=node_status,
        law_proposed=law_counts,
        law_accepted=law_accepted,
        error_messages=errors,
    )


def run_trial(case: Dict[str, Any],
              provider: LLMProvider,
              repeat: int,
              config_name: str,
              max_retries: int = 4,
              budget: int = 30,
              law_set: Optional[List[str]] = None,
              max_depth: int = 6) -> Dict[str, Any]:
    inst = InstrumentedProvider(provider, budget)
    spec = parse_spec(case["spec"])
    graph = RefinementGraph(spec)
    engine = RefinementEngine()
    if law_set is not None:
        # Restrict the engine so the law set is the only variable between arms.
        # The refiner reads engine.laws for both TOTAL_LAWS and the prompt, so
        # filtering here removes the law from advertising, parsing and search.
        engine.laws = {k: v for k, v in engine.laws.items() if k in law_set}
    refiner = AutomatedRefiner(engine, inst, max_retries=max_retries,
                               max_depth=max_depth)

    t0 = time.time()
    outcome = "UNKNOWN"
    detail = ""
    program = None
    program_python = None
    try:
        ok = refiner.refine_node(graph, graph.root_id)
        if ok and graph.is_complete(graph.root_id):
            outcome = "SUCCESS"
            program_ast = graph.reconstruct_program()
            program = program_to_str(program_ast)
            # Executable form of the *verified* tree. Emitting it here rather
            # than re-deriving it later keeps the code that runs identical to
            # the code the prover accepted.
            try:
                program_python = to_python(program_ast)
            except Exception as e:
                detail = f"program emitted but to_python failed: {type(e).__name__}: {e}"
        else:
            outcome = "FAILED"
            detail = "refiner returned without completing the root node"
    except RefinementExhausted as e:
        outcome = "EXHAUSTED"
        detail = str(e)
    except BudgetExhausted as e:
        outcome = "BUDGET"
        detail = str(e)
    except RecursionError as e:
        outcome = "RECURSION"
        detail = str(e)
    except Exception as e:
        outcome = "ERROR"
        detail = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"
    wall = time.time() - t0

    calls = inst.calls
    lat = [c["latency_s"] for c in calls]
    return dict(
        config=config_name,
        case_id=case["id"],
        tier=case["tier"],
        repeat=repeat,
        outcome=outcome,
        detail=detail,
        program=program,
        program_python=program_python,
        law_set=sorted(engine.laws),
        wall_s=round(wall, 2),
        llm_calls=len(calls),
        llm_time_s=round(sum(lat), 2),
        mean_latency_s=round(sum(lat) / len(lat), 2) if lat else None,
        output_tokens=sum(c["output_tokens"] or 0 for c in calls),
        prompt_tokens=sum(c["prompt_tokens"] or 0 for c in calls),
        thinking_channel_used=any(c.get("used_thinking_channel") for c in calls),
        graph=summarise_graph(graph),
        raw_responses=[c["response"] for c in calls],
    )
