"""Tables for Study 3, generated from the stored result rows.

    python benchmarks/analyse_study3.py > benchmarks/results/study3_tables.md
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PRE = "benchmarks/results/results_study3_prefix.jsonl"
POST = "benchmarks/results/results_study3_v2.jsonl"


def load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def last_per_config(rows, arm):
    """Keep the final row per config.

    Two background runs were killed mid-flight by memory pressure and wrote a
    partial row before dying; the config was then re-run on its own. Taking the
    last row keeps the clean re-run rather than the interrupted one.
    """
    out = {}
    for r in rows:
        if r.get("arm") == arm:
            out[r["config"]] = r
    return out


def verdict(row):
    if row.get("all_passed"):
        return "PASS"
    status = row.get("status") or ""
    if status.startswith("no_program"):
        return status[len("no_program "):].strip("()")
    return {"timeout": "TIMEOUT (loops forever)",
            "exec_error": "does not run",
            "crash": "crashed",
            "no_function": "no function"}.get(status, f"{row.get('passed')}/{row.get('total')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre", default=PRE)
    ap.add_argument("--post", default=POST)
    args = ap.parse_args()

    pre, post = load(args.pre), load(args.post)

    pre = [r for r in pre if r.get("config") != "oracle"]
    post = [r for r in post if r.get("config") != "oracle"]
    direct = last_per_config(pre, "direct")
    refine_pre = last_per_config(pre, "refinement")
    refine_post = last_per_config(post, "refinement")

    # Oracle rows in older result files are scripted, not measured; they are
    # excluded rather than presented next to model results.
    order = [c for c in ["gpt-oss-120b", "qwen3-coder-next", "llama3.1",
                         "qwen3.5-nothink", "qwen3.5-think", "ornith", "ornith-think"]
             if c in direct or c in refine_pre or c in refine_post]

    print("### Both arms, per model\n")
    print("| Model | Direct: tests passed | Direct verdict | Refinement (v1) | Refinement (v2, escaping fixed) |")
    print("|---|---|---|---|---|")
    for cfg in order:
        d = direct.get(cfg)
        r1 = refine_pre.get(cfg)
        r2 = refine_post.get(cfg) or (r1 if cfg == "oracle" else None)
        dcell = f"{d['passed']}/{d['total']}" if d else "--"
        dverd = verdict(d) if d else "-- (cannot write code)"
        print(f"| `{cfg}` | {dcell} | {dverd} | "
              f"{verdict(r1) if r1 else '--'} | {verdict(r2) if r2 else '--'} |")

    print("\n### Refinement arm detail\n")
    print("| Model | v1 outcome | v1 calls | v2 outcome | v2 calls | v2 laws accepted |")
    print("|---|---|---|---|---|---|")
    for cfg in order:
        r1, r2 = refine_pre.get(cfg), refine_post.get(cfg)
        if cfg == "oracle":
            r2 = r2 or r1
        print(f"| `{cfg}` | {r1['refine_outcome'] if r1 else '--'} | "
              f"{r1.get('llm_calls', '--') if r1 else '--'} | "
              f"{r2['refine_outcome'] if r2 else '--'} | "
              f"{r2.get('llm_calls', '--') if r2 else '--'} | "
              f"{r2.get('law_accepted') if r2 else '--'} |")

    n_direct_pass = sum(1 for c, r in direct.items() if r.get("all_passed"))
    n_refine1 = sum(1 for c, r in refine_pre.items() if r.get("all_passed"))
    n_refine2 = sum(1 for c, r in refine_post.items() if r.get("all_passed"))
    print(f"\nDirect arm passing all 12 inputs: {n_direct_pass}/{len(direct)}")
    print(f"Refinement arm (v1) passing: {n_refine1}/{len(refine_pre)}")
    print(f"Refinement arm (v2) passing: {n_refine2}/{len(refine_post)}")


if __name__ == "__main__":
    main()
