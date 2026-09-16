"""Compare the 5-core-law engine against the 9-law engine (extended laws).

Both arms use the same models, cases, budget and temperature; the only variable
is the law set available to the refiner.

    python benchmarks/compare_laws.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.cases import CASES

# Both arms live in one file, distinguished by the `law_arm` field, so that
# they provably share the same engine build and harness settings.
RESULTS = "benchmarks/results/results_lawcmp.jsonl"
NEW_LAWS = {"strengthen_post", "weaken_pre", "initialized_skip", "flexible_sequential"}


def load(arm):
    if not os.path.exists(RESULTS):
        return []
    out = []
    with open(RESULTS, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("law_arm") == arm:
                out.append(rec)
    return out


def md(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def rate(recs):
    if not recs:
        return None
    return sum(1 for r in recs if r["outcome"] == "SUCCESS"), len(recs)


def main():
    core, ext = load("core"), load("extended")
    configs = [c for c in ("llama3.1", "qwen3.5-nothink")
               if any(r["config"] == c for r in ext)]

    ci = defaultdict(list)
    ei = defaultdict(list)
    for r in core:
        ci[(r["config"], r["case_id"])].append(r)
    for r in ext:
        ei[(r["config"], r["case_id"])].append(r)

    print("# Core laws (5) vs Extended laws (9)\n")
    print("Same models, cases, budget (30) and temperature (0.2).\n")

    print("## Per-case: core -> extended\n")
    rows = []
    for c in CASES:
        row = [c["id"], c["tier"]]
        for cfg in configs:
            a, b = rate(ci[(cfg, c["id"])]), rate(ei[(cfg, c["id"])])
            fa = f"{a[0]}/{a[1]}" if a else "-"
            fb = f"{b[0]}/{b[1]}" if b else "-"
            arrow = ""
            if a and b:
                da = a[0] / a[1] if a[1] else 0
                db = b[0] / b[1] if b[1] else 0
                arrow = "  **UP**" if db > da else ("  down" if db < da else "")
            row.append(f"{fa} -> {fb}{arrow}")
        rows.append(row)
    print(md(["Case", "Tier"] + configs, rows))

    print("\n## Aggregate\n")
    rows = []
    for cfg in configs:
        for label, idx in (("core (5 laws)", ci), ("extended (9 laws)", ei)):
            recs = [r for k, v in idx.items() if k[0] == cfg for r in v]
            if not recs:
                continue
            n = sum(1 for r in recs if r["outcome"] == "SUCCESS")
            calls = sum(r["llm_calls"] for r in recs)
            err = budget_err = 0
            for r in recs:
                for m in r["graph"]["error_messages"]:
                    if "budget" in m.lower():
                        budget_err += 1
                    else:
                        err += 1
            rows.append([
                cfg, label, f"{n}/{len(recs)} ({100*n/len(recs):.0f}%)",
                f"{calls/len(recs):.1f}",
                f"{sum(r['wall_s'] for r in recs)/len(recs):.1f}",
                f"{err}/{calls} ({100*err/calls:.0f}%)" if calls else "-",
                sum(1 for r in recs if r["outcome"] == "BUDGET"),
            ])
    print(md(["Config", "Law set", "Solved", "Calls/case", "Wall s/case",
              "Malformed", "Budget aborts"], rows))

    print("\n## Did the models actually reach for the new laws?\n")
    rows = []
    for cfg in configs:
        recs = [r for k, v in ei.items() if k[0] == cfg for r in v]
        prop, acc = Counter(), Counter()
        for r in recs:
            prop.update(r["graph"]["law_proposed"])
            acc.update(r["graph"]["law_accepted"])
        total = sum(prop.values())
        for law in sorted(NEW_LAWS):
            rows.append([cfg, law, prop.get(law, 0), acc.get(law, 0),
                         f"{100*prop.get(law,0)/total:.1f}%" if total else "-"])
    print(md(["Config", "New law", "Proposed", "Accepted", "Share of proposals"], rows))

    print("\n## Full law histogram, extended arm (proposed -> accepted)\n")
    laws = ["assignment", "skip", "sequential", "alternation", "iteration",
            "strengthen_post", "weaken_pre", "initialized_skip",
            "flexible_sequential", "unknown"]
    rows = []
    for cfg in configs:
        recs = [r for k, v in ei.items() if k[0] == cfg for r in v]
        prop, acc = Counter(), Counter()
        for r in recs:
            prop.update(r["graph"]["law_proposed"])
            acc.update(r["graph"]["law_accepted"])
        rows.append([cfg] + [f"{prop.get(l,0)}->{acc.get(l,0)}" for l in laws])
    print(md(["Config"] + laws, rows))

    print("\n## Errors in the extended arm\n")
    for cfg in configs:
        recs = [r for k, v in ei.items() if k[0] == cfg for r in v]
        msgs = Counter()
        for r in recs:
            for m in r["graph"]["error_messages"]:
                if "budget" in m.lower():
                    continue
                msgs[m.split("\n")[0][:100]] += 1
        print(f"\n### {cfg}")
        if not msgs:
            print("(none)")
        for m, n in msgs.most_common(8):
            print(f"- `{m}` x{n}")

    print("\n## Programs found in the extended arm\n")
    seen = set()
    for cfg in configs:
        for c in CASES:
            for r in ei.get((cfg, c["id"]), []):
                if r["outcome"] == "SUCCESS" and r["program"] and (cfg, c["id"]) not in seen:
                    seen.add((cfg, c["id"]))
                    print(f"\n**{cfg} / {c['id']}**\n```\n{r['program']}\n```")


if __name__ == "__main__":
    main()
