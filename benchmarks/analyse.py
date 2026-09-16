"""Aggregate benchmark results into the tables used by the report."""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.cases import CASES, CASES_BY_ID

CONFIG_ORDER = ["oracle", "llama3.1", "llama3.1-wide", "qwen3.5-nothink",
                "qwen3.5-think", "ornith", "ornith-think"]


def load(paths):
    recs = []
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    return recs


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def main():
    recs = load(["benchmarks/results/oracle.jsonl", "benchmarks/results/results.jsonl"])
    by = defaultdict(list)
    for r in recs:
        by[(r["config"], r["case_id"])].append(r)

    configs = [c for c in CONFIG_ORDER if any(k[0] == c for k in by)]
    # A case counts as solvable once ANY arm has actually produced a verified
    # program for it. The oracle is a lower bound on solvability, not a ceiling:
    # a model may find a refinement the hand-written playbook never scripted.
    solvable, shown_by = set(), {}
    for c in CASES:
        for cfg in configs:
            if any(x["outcome"] == "SUCCESS" for x in by.get((cfg, c["id"]), [])):
                solvable.add(c["id"])
                shown_by.setdefault(c["id"], cfg)

    print("## Per-case outcomes (successes / attempts)\n")
    headers = ["Case", "Tier", "Solvable?"] + configs[1:]
    rows = []
    for c in CASES:
        mark = f"yes (first: {shown_by[c['id']]})" if c["id"] in solvable else "none found"
        row = [c["id"], c["tier"], mark]
        for cfg in configs[1:]:
            rs = by.get((cfg, c["id"]), [])
            n = len(rs)
            s = sum(1 for x in rs if x["outcome"] == "SUCCESS")
            oc = Counter(x["outcome"] for x in rs if x["outcome"] != "SUCCESS")
            extra = " " + ",".join(f"{k.lower()}x{v}" for k, v in oc.most_common(2)) if oc else ""
            row.append(f"{s}/{n}{extra}")
        rows.append(row)
    print(md_table(headers, rows))

    print("\n## Aggregate per configuration\n")
    headers = ["Config", "Trials solved (solvable cases)", "Trials solved (all cases)", "LLM calls/case",
               "Wall s/case", "Mean latency s", "Malformed output", "Z3-rejected", "Budget aborts"]
    rows = []
    for cfg in configs:
        rs = [x for k, v in by.items() if k[0] == cfg for x in v]
        if not rs:
            continue
        solv = [x for x in rs if x["case_id"] in solvable]
        n_sol = sum(1 for x in solv if x["outcome"] == "SUCCESS")
        n_all = sum(1 for x in rs if x["outcome"] == "SUCCESS")
        calls = sum(x["llm_calls"] for x in rs)
        # A child's BudgetExhausted propagates into the parent's broad
        # `except Exception`, so it is logged as an attempt error. Those are
        # harness aborts, not malformed model output -- count them separately.
        err = budget_err = 0
        for x in rs:
            for m in x["graph"]["error_messages"]:
                if "budget" in m.lower():
                    budget_err += 1
                else:
                    err += 1
        rej = sum(x["graph"]["attempt_status"].get("rejected", 0) for x in rs)
        lats = [x["mean_latency_s"] for x in rs if x["mean_latency_s"]]
        rows.append([
            cfg,
            f"{n_sol}/{len(solv)} ({100*n_sol/len(solv):.0f}%)",
            f"{n_all}/{len(rs)} ({100*n_all/len(rs):.0f}%)",
            f"{calls/len(rs):.1f}",
            f"{sum(x['wall_s'] for x in rs)/len(rs):.1f}",
            f"{sum(lats)/len(lats):.1f}" if lats else "-",
            f"{err}/{calls} ({100*err/calls:.0f}%)" if calls else "-",
            rej,
            sum(1 for x in rs if x["outcome"] == "BUDGET"),
        ])
    print(md_table(headers, rows))

    print("\n## Law selection (proposed -> accepted by Z3)\n")
    laws = ["assignment", "skip", "sequential", "alternation", "iteration", "unknown"]
    rows = []
    for cfg in configs[1:]:
        rs = [x for k, v in by.items() if k[0] == cfg for x in v]
        prop, acc = Counter(), Counter()
        for x in rs:
            prop.update(x["graph"]["law_proposed"])
            acc.update(x["graph"]["law_accepted"])
        rows.append([cfg] + [f"{prop.get(l,0)} -> {acc.get(l,0)}" for l in laws])
    print(md_table(["Config"] + laws, rows))

    print("\n## Failure taxonomy (error messages from malformed proposals)\n")
    for cfg in configs[1:]:
        rs = [x for k, v in by.items() if k[0] == cfg for x in v]
        msgs = Counter()
        for x in rs:
            for m in x["graph"]["error_messages"]:
                if "budget" in m.lower():
                    continue          # harness abort, not a model output defect
                msgs[m.split("\n")[0][:110]] += 1
        print(f"\n### {cfg}")
        if not msgs:
            print("(none)")
        for m, n in msgs.most_common(8):
            print(f"- `{m}` x{n}")

    print("\n## Example synthesised programs\n")
    for cfg in configs:
        for c in CASES:
            for x in by.get((cfg, c["id"]), []):
                if x["outcome"] == "SUCCESS" and x["program"]:
                    print(f"\n**{cfg} / {c['id']}**\n```\n{x['program']}\n```")
                    break
            else:
                continue
            break


if __name__ == "__main__":
    main()
