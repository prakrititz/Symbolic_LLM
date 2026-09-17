"""Study 3: the same specification, with and without the refinement calculus.

Both arms ask the same models for a Python implementation of the same
specification. They differ only in how the code is produced:

  direct      -- the model writes the function itself (the paper's "NL + FS"
                 baseline column). Nothing checks it; whatever it writes is what
                 runs.
  refinement  -- the model only chooses refinement laws and their parameters.
                 Every step is discharged by Z3, and the Python is *emitted from
                 the verified refinement tree*, not written by the model.

Both arms' code is written to disk and executed against identical inputs, so a
reader can open the two files and compare them directly. That is the point of
the study: the refinement arm's code should be correct by construction, and the
direct arm's should show the failure modes the paper reports in Figure 1 --
wrong bounds, and loops that never terminate.

    FORMALLLM_REMOTE_AUTH=... python benchmarks/study3.py --configs all
"""
import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.cases import CASES_BY_ID
from benchmarks.baseline_cases import BASELINE, UNSATISFIABLE
from benchmarks.baseline import (PROMPT, PROMPT_NO_STDLIB, extract_code,
                                 run_generated, score, make_code_provider,
                                 uses_library)
from benchmarks.run_bench import CONFIGS, LAW_SETS, expand_configs, make_provider
from benchmarks.harness import run_trial

from FormalLLM.lpl.to_python import to_python

CODE_ROOT = "benchmarks/study3_code"


def wrap_as_function(program_src: str, signature: str, output_var: str) -> str:
    """Wrap an emitted L_pl program body in the benchmark's function signature.

    The refined program operates on the specification's variables directly --
    it assigns `x`, it does not return anything -- so to score it with the same
    checker as the direct arm we bind the inputs as parameters and return the
    output variable. Nothing here alters the program's logic.

    The output variable is deliberately *not* pre-initialised: if the refinement
    produced a loop whose body reads `x` before any step assigns it, that is a
    real defect in the refinement and should surface as a NameError, not be
    papered over with a default value.
    """
    body = "\n".join(f"    {line}" if line.strip() else line
                     for line in program_src.splitlines())
    return f"{signature}\n{body}\n    return {output_var}\n"


def refinement_arm(case, cfg_name, cfg, repeat, args):
    """Refine the spec with the model, then emit and score Python from the tree."""
    spec = BASELINE[case["id"]]
    provider = make_provider(cfg, args.temperature, args.timeout)

    t0 = time.time()
    rec = run_trial(case, provider, repeat, cfg_name,
                    max_retries=args.max_retries, budget=args.budget,
                    law_set=LAW_SETS[args.laws], max_depth=args.max_depth)
    wall = time.time() - t0

    row = dict(
        arm="refinement", config=cfg_name, model=cfg.get("model"),
        case_id=case["id"], repeat=repeat,
        refine_outcome=rec["outcome"], llm_calls=rec["llm_calls"],
        wall_s=round(wall, 1), code_path=None, passed=0,
        total=len(spec["inputs"]), status=None, all_passed=False,
        law_accepted=rec["graph"]["law_accepted"],
        detail=rec.get("detail", "")[:300],
    )

    if rec["outcome"] != "SUCCESS":
        row["status"] = f"no_program ({rec['outcome']})"
        return row

    # Python emitted by the harness directly from the verified tree, so the code
    # that runs here is the code the prover accepted.
    program_src = rec.get("program_python")
    if not program_src:
        row["status"] = "emit_failed"
        return row

    outdir = os.path.join(CODE_ROOT, cfg_name)
    os.makedirs(outdir, exist_ok=True)
    suffix = "" if args.repeats == 1 else f"_r{repeat}"
    path = os.path.join(outdir, f"{case['id']}_refined{suffix}.py")

    header = (f"# arm:    refinement (code EMITTED from the verified refinement tree)\n"
              f"# model:  {cfg.get('model')} -- chose laws only, wrote no code\n"
              f"# case:   {case['id']} -- {case['title']}\n"
              f"# laws:   {rec['graph']['law_accepted']}\n"
              f"# calls:  {rec['llm_calls']} LLM calls, every step discharged by Z3\n\n")
    source = wrap_as_function(program_src, spec["signature"], args.output_var)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + source)

    outcome = run_generated(path, spec["inputs"], timeout=args.exec_timeout)
    passed, total, note = score(case["id"], outcome)
    row.update(code_path=path, passed=passed, total=total,
               status=outcome.get("status"), note=note,
               all_passed=(passed == total and total > 0))
    return row


def direct_arm(case, cfg_name, cfg, repeat, args, no_stdlib=False):
    """Ask the model for the function outright -- no calculus, no prover.

    With `no_stdlib` the model is forbidden library calls, so it must synthesise
    the algorithm. This is the like-for-like comparison with the refinement arm,
    whose L_pl has no function calls: without it a model can answer the paper's
    square-root specification with `math.sqrt` and never attempt the algorithm
    the specification describes.
    """
    spec = BASELINE[case["id"]]
    provider = make_code_provider(cfg, args.temperature, args.timeout)

    template = PROMPT_NO_STDLIB if no_stdlib else PROMPT
    prompt = template.format(nl=spec["nl"], spec=case["spec"].strip(),
                             signature=spec["signature"])
    t0 = time.time()
    try:
        raw = provider.generate(prompt)
        error = None
    except Exception as e:
        raw, error = "", f"{type(e).__name__}: {e}"
    latency = time.time() - t0

    outdir = os.path.join(CODE_ROOT, cfg_name)
    os.makedirs(outdir, exist_ok=True)
    suffix = "" if args.repeats == 1 else f"_r{repeat}"
    tag = "direct_nostdlib" if no_stdlib else "direct"
    path = os.path.join(outdir, f"{case['id']}_{tag}{suffix}.py")

    code = extract_code(raw)
    header = (f"# arm:    {tag} (model wrote this code itself; nothing verified it)\n"
              f"# model:  {cfg.get('model')}\n"
              f"# case:   {case['id']} -- {case['title']}\n"
              f"# intent: {spec['nl']}\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + (code or "# (model produced no code)\n"))

    outcome = run_generated(path, spec["inputs"], timeout=args.exec_timeout)
    passed, total, note = score(case["id"], outcome)
    violations = uses_library(code or "")
    return dict(
        arm=tag, config=cfg_name, model=cfg.get("model"),
        used_library=violations,
        case_id=case["id"], repeat=repeat, refine_outcome=None,
        llm_calls=1, wall_s=round(latency, 1), code_path=path,
        passed=passed, total=total, status=outcome.get("status"), note=note,
        all_passed=(passed == total and total > 0),
        transport_error=error,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["high-end", "local"])
    ap.add_argument("--cases", nargs="+", default=["C5-sqrt-paper"])
    ap.add_argument("--arms", nargs="+", default=["direct", "refinement"],
                    choices=["direct", "direct_nostdlib", "refinement"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--max-retries", type=int, default=4)
    ap.add_argument("--budget", type=int, default=15)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--exec-timeout", type=int, default=10,
                    help="wall-clock limit for the generated code; the paper's "
                         "point is that unverified code loops forever, so this "
                         "is what catches it")
    ap.add_argument("--laws", choices=sorted(LAW_SETS), default="all")
    ap.add_argument("--output-var", default="x",
                    help="the specification variable the wrapped function returns")
    ap.add_argument("--lenient-variant", action="store_true",
                    help="Disable the 0 <= V strict variant bound check (for ablation studies)")
    ap.add_argument("--out", default="benchmarks/results/results_study3.jsonl")
    args = ap.parse_args()
    
    if args.lenient_variant:
        os.environ["FORMALLLM_STRICT_VARIANT"] = "0"
    
    # Compulsory: always run both arms to compare direct vs refinement
    args.arms = ["direct", "refinement"]

    configs = expand_configs(args.configs)
    cases = [CASES_BY_ID[c] for c in args.cases]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(CODE_ROOT, exist_ok=True)
    started = time.time()

    with open(args.out, "a", encoding="utf-8") as fh:
        for cfg_name in configs:
            cfg = CONFIGS[cfg_name]
            for case in cases:
                if case["id"] not in BASELINE:
                    print(f"  !! {case['id']} has no BASELINE entry; skipped")
                    continue
                for repeat in range(args.repeats):
                    for arm in args.arms:
                        try:
                            if arm == "refinement":
                                row = refinement_arm(case, cfg_name, cfg, repeat, args)
                            else:
                                row = direct_arm(case, cfg_name, cfg, repeat, args,
                                                 no_stdlib=(arm == "direct_nostdlib"))
                        except Exception as e:
                            row = dict(arm=arm, config=cfg_name, case_id=case["id"],
                                       repeat=repeat, status="harness_error",
                                       all_passed=False, passed=0,
                                       total=len(BASELINE[case["id"]]["inputs"]),
                                       detail=f"{type(e).__name__}: {e}",
                                       traceback=traceback.format_exc(limit=4))
                        row["temperature"] = args.temperature
                        fh.write(json.dumps(row, default=str) + "\n")
                        fh.flush()
                        flag = "PASS" if row.get("all_passed") else "fail"
                        print(f"[{time.time()-started:7.1f}s] {cfg_name:17s} "
                              f"{case['id']:15s} {arm:10s} {flag} "
                              f"{row.get('passed',0):2d}/{row.get('total',0):2d} "
                              f"{str(row.get('status') or ''):22s} "
                              f"{row.get('wall_s', 0):7.1f}s", flush=True)

    print(f"\nDone in {time.time()-started:.1f}s -> {args.out}")
    print(f"Generated code under {CODE_ROOT}/<config>/")


if __name__ == "__main__":
    main()
