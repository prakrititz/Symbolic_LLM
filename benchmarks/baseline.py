"""Run the direct code-generation baseline and store each model's code.

Generated code is executed in a separate process with a wall-clock timeout, so a
model that emits an infinite loop cannot hang the run.

Usage:
    python benchmarks/baseline.py --configs llama3.1 qwen3.5-nothink ornith
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.cases import CASES
from benchmarks.baseline_cases import BASELINE, UNSATISFIABLE
from benchmarks.run_bench import CONFIGS, REMOTE_BASE_URL, expand_configs
from FormalLLM.llm.provider import OllamaProvider, OpenAIChatProvider

CODE_ROOT = "benchmarks/baseline_code"

PROMPT = """You are given a formal specification in a refinement-calculus \
specification language, together with its intent in English.

Intent:
{nl}

Formal specification:
{spec}

Write a single, self-contained Python function implementing this specification.

Requirements:
- Use exactly this signature: {signature}
- Return the value(s) described; do not print anything.
- Use only the Python standard library.
- Output ONLY the code. No markdown fences, no explanation, no tests.
"""


def extract_code(text: str) -> str:
    """Pull Python source out of a model reply, tolerating markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if fence:
        return fence.group(1).strip()
    if text.startswith("```"):                     # unterminated fence
        text = re.sub(r"^```(?:python)?\s*\n?", "", text)
    # Drop any prose before the first def/import line.
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(("def ", "import ", "from ")):
            return "\n".join(lines[i:]).strip()
    return text


# The unrestricted prompt above lets a model answer `sqrt(N)` with
# `math.sqrt(N)`. That is correct code, but it does not attempt the algorithm
# the specification describes, so it cannot exhibit the defects the paper's
# Figure 1 is about -- and it is not comparable with the refinement arm, whose
# L_pl has no function calls at all. This variant removes the shortcut, making
# both arms synthesise the algorithm.
PROMPT_NO_STDLIB = PROMPT.rstrip() + """
- Do NOT import any module, and do NOT call any library function.
  In particular math.sqrt, math.pow, abs, min, max, sorted and the ** operator
  are all forbidden. Use only arithmetic (+ - * /), comparisons, assignment,
  while loops and if statements -- the same constructs the specification
  language provides.
"""

#: Constructs that mean the model took a library shortcut rather than
#: synthesising the algorithm.
LIBRARY_MARKERS = ("import ", "math.", "sqrt", "**", "abs(", "min(", "max(",
                   "sorted(", "pow(")


def uses_library(code: str) -> list:
    """Which forbidden constructs appear in `code` (ignoring comments)."""
    body = "\n".join(l for l in code.splitlines() if not l.lstrip().startswith("#"))
    return [m for m in LIBRARY_MARKERS if m in body]


RUNNER = r'''
import json, sys
sys.setrecursionlimit(10000)
ns = {}
try:
    exec(open(sys.argv[1], encoding="utf-8").read(), ns)
except Exception as e:
    print(json.dumps({"status": "exec_error", "error": f"{type(e).__name__}: {e}"}))
    sys.exit(0)
fn = ns.get("f")
if not callable(fn):
    print(json.dumps({"status": "no_function"}))
    sys.exit(0)
results = []
for args in json.loads(sys.argv[2]):
    try:
        results.append({"args": args, "value": fn(*args), "error": None})
    except Exception as e:
        results.append({"args": args, "value": None, "error": f"{type(e).__name__}: {e}"})
print(json.dumps({"status": "ok", "results": results}, default=str))
'''


def run_generated(path, inputs, timeout=10):
    runner = os.path.join(os.path.dirname(path), "_runner.py")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(RUNNER)
    try:
        proc = subprocess.run(
            [sys.executable, runner, path, json.dumps([list(a) for a in inputs])],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    finally:
        if os.path.exists(runner):
            os.remove(runner)
    if proc.returncode != 0:
        return {"status": "crash", "error": (proc.stderr or "")[-400:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "bad_output", "error": (proc.stdout or "")[-400:]}


def score(case_id, outcome):
    """-> (passed, total, note)"""
    spec = BASELINE[case_id]
    if outcome.get("status") != "ok":
        return 0, len(spec["inputs"]), outcome.get("status")
    passed = 0
    for row in outcome["results"]:
        if row["error"] is not None:
            continue
        try:
            if spec["check"](tuple(row["args"]), row["value"]):
                passed += 1
        except Exception:
            pass
    return passed, len(outcome["results"]), None


def make_code_provider(cfg, temperature, timeout):
    """A provider configured for free-form code, not a JSON law choice.

    `response_format` is left unset in both branches: this arm wants Python
    source, and constraining the reply to a JSON object would make the model
    wrap its code in a string.
    """
    if cfg["kind"] == "openai":
        return OpenAIChatProvider(
            model_name=cfg["model"],
            base_url=REMOTE_BASE_URL,
            temperature=temperature,
            max_tokens=2048,
            response_format=None,
            timeout=timeout,
        )
    return OllamaProvider(
        model_name=cfg["model"], think=cfg["think"],
        # Reasoning models spend hundreds of tokens thinking before the
        # answer; too small a cap truncates them mid-thought.
        options={"temperature": temperature,
                 "num_predict": 4096 if cfg["think"] else 900},
        response_format=None,      # free-form text: we want code, not JSON
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+",
                    default=["llama3.1", "qwen3.5-nothink", "qwen3.5-think",
                             "ornith", "ornith-think"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--timeout", type=int, default=900,
                    help="per-call timeout in seconds for hosted models")
    ap.add_argument("--cases", nargs="+", default=None)
    ap.add_argument("--out", default="benchmarks/results/baseline.jsonl")
    args = ap.parse_args()
    args.configs = expand_configs(args.configs)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    started = time.time()

    with open(args.out, "a", encoding="utf-8") as fh:
        for cfg_name in args.configs:
            cfg = CONFIGS[cfg_name]
            outdir = os.path.join(CODE_ROOT, cfg_name)
            os.makedirs(outdir, exist_ok=True)
            provider = make_code_provider(cfg, args.temperature, args.timeout)
            # Plain text, not JSON: this baseline wants code, not a law choice.
            provider_generate = provider.generate

            for case in CASES:
                if args.cases is not None and case["id"] not in args.cases:
                    continue
                if case["id"] not in BASELINE:
                    continue
                spec = BASELINE[case["id"]]
                for r in range(args.repeats):
                    prompt = PROMPT.format(nl=spec["nl"], spec=case["spec"].strip(),
                                           signature=spec["signature"])
                    t0 = time.time()
                    try:
                        raw = provider_generate(prompt)
                    except Exception as e:
                        raw = ""
                        print(f"  !! {cfg_name} {case['id']}: {e}")
                    latency = time.time() - t0

                    code = extract_code(raw)
                    suffix = "" if args.repeats == 1 else f"_r{r}"
                    path = os.path.join(outdir, f"{case['id']}{suffix}.py")
                    header = (f"# model:  {cfg['model']} (think={cfg['think']})\n"
                              f"# case:   {case['id']} -- {case['title']}\n"
                              f"# spec:   {case['spec'].strip().splitlines()[0]}\n"
                              f"#         {case['spec'].strip().splitlines()[-1]}\n"
                              f"# intent: {spec['nl']}\n\n")
                    with open(path, "w", encoding="utf-8") as cf:
                        cf.write(header + (code or "# (model produced no code)\n"))

                    outcome = run_generated(path, spec["inputs"])
                    passed, total, note = score(case["id"], outcome)
                    rec = dict(
                        config=cfg_name, case_id=case["id"], tier=case["tier"],
                        repeat=r, code_path=path, latency_s=round(latency, 2),
                        passed=passed, total=total, status=outcome.get("status"),
                        note=note, all_passed=(passed == total and total > 0),
                        unsatisfiable=case["id"] in UNSATISFIABLE,
                        raw_chars=len(raw),
                    )
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    flag = "PASS" if rec["all_passed"] else "fail"
                    print(f"[{time.time()-started:6.1f}s] {cfg_name:16s} "
                          f"{case['id']:20s} {flag} {passed:2d}/{total:2d} "
                          f"{outcome.get('status',''):12s} {latency:5.1f}s",
                          flush=True)

    print(f"\nDone in {time.time()-started:.1f}s -> {args.out}")
    print(f"Generated code stored under {CODE_ROOT}/<config>/<case>.py")


if __name__ == "__main__":
    main()
