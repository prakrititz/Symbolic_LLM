"""
results_viewer.py — terminal viewer for Refine4LLM benchmark JSONL files.

Usage:
    python benchmarks/results_viewer.py                         # auto-detect newest JSONL
    python benchmarks/results_viewer.py results_extended.jsonl  # specific file
    python benchmarks/results_viewer.py --errors                # show parser error breakdown
    python benchmarks/results_viewer.py --case A2-assign        # drill into one case
"""
import sys
import os
import json
import argparse
import re
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

def col(text, colour): return f"{colour}{text}{RESET}"
def bold(text):        return col(text, BOLD)
def dim(text):         return col(text, DIM)

OUTCOME_COLOUR = {
    "SUCCESS":   GREEN,
    "BUDGET":    YELLOW,
    "EXHAUSTED": RED,
    "ERROR":     RED,
}

def outcome_badge(outcome: str) -> str:
    c = OUTCOME_COLOUR.get(outcome, RESET)
    return col(f" {outcome:<9}", c)

# ── Data loading ──────────────────────────────────────────────────────────────
def load(path: Path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def pick_file(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = RESULTS_DIR / p
        return p
    # newest JSONL in results/
    candidates = sorted(RESULTS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        sys.exit("No .jsonl files found in benchmarks/results/")
    return candidates[0]

# ── Summary table ─────────────────────────────────────────────────────────────
def print_summary(rows):
    # Group: (config, tier, case_id)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["config"], r["tier"], r["case_id"])].append(r)

    print()
    print(bold(f"  {'Config':<14} {'Tier':<6} {'Case':<22} {'Pass':<5} {'Avg calls':<11} {'Avg wall(s)':<12} {'Top errors'}"))
    print(dim("  " + "─" * 110))

    prev_config = None
    for (config, tier, case_id), repeats in sorted(groups.items()):
        if config != prev_config:
            print()
            print(col(f"  ▶ {config}", CYAN + BOLD))
            prev_config = config

        n      = len(repeats)
        passed = sum(1 for r in repeats if r["outcome"] == "SUCCESS")
        rate   = f"{passed}/{n}"
        avg_calls = sum(r["llm_calls"] for r in repeats) / n
        avg_wall  = sum(r["wall_s"]    for r in repeats) / n

        # most common error category
        all_errs = []
        for r in repeats:
            all_errs.extend(r["graph"].get("error_messages", []))
        top_err = _top_error(all_errs)

        badge = outcome_badge("SUCCESS" if passed == n else ("BUDGET" if passed == 0 else "BUDGET"))
        if passed == n:    badge = outcome_badge("SUCCESS")
        elif passed == 0:  badge = outcome_badge(repeats[-1]["outcome"])
        else:              badge = outcome_badge("BUDGET")

        print(f"  {config:<14} {col(tier, MAGENTA):<12} {case_id:<22} {badge} {rate:<5}  {avg_calls:<9.1f}  {avg_wall:<12.1f}  {dim(top_err)}")

    print()

def _top_error(errors):
    """Return a short label for the most frequent error kind."""
    if not errors: return "—"
    cats = defaultdict(int)
    for e in errors:
        if "&&" in e or "∧" in e:
            cats["& / ∧ operator (use /\\)"] += 1
        elif "budget" in e.lower():
            cats["budget exhausted"] += 1
        elif "Unknown law" in e:
            cats["unknown law"] += 1
        elif "/\\" in e and "SLASH" in e:
            cats["/\\ escape mismatch"] += 1
        elif "and" in e:
            cats["'and' keyword (use /\\)"] += 1
        else:
            cats["parse error"] += 1
    top = max(cats, key=cats.__getitem__)
    return f"{top} ×{cats[top]}"

# ── Error breakdown ────────────────────────────────────────────────────────────
def print_errors(rows):
    cats = defaultdict(int)
    examples = defaultdict(list)
    for r in rows:
        for e in r["graph"].get("error_messages", []):
            label = _classify_error(e)
            cats[label] += 1
            if len(examples[label]) < 2:
                # grab the first line of the raw error
                examples[label].append(e.split("\n")[0][:90])

    print()
    print(bold("  Error breakdown across all runs"))
    print(dim("  " + "─" * 70))
    for label, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {col(f'{count:>5}', YELLOW)}  {label}")
        for ex in examples[label]:
            print(dim(f"           {ex}"))
    print()

def _classify_error(e):
    if "&&" in e:            return "C-style &&  (should be /\\)"
    if "∧" in e:             return "Unicode ∧  (should be /\\)"
    if "'and'" in e:         return "keyword 'and'  (should be /\\)"
    if "'\\/'" in e or "\\/" in e: return "\\/  disjunction parse fail"
    if "SLASH" in e and "/\\" in e: return "/\\ escape mismatch inside JSON"
    if "budget" in e.lower(): return "LLM call budget exhausted"
    if "Unknown law" in e:   return "Unknown law name"
    return "other parse error"

# ── Case drilldown ─────────────────────────────────────────────────────────────
def print_case(rows, case_id):
    matching = [r for r in rows if r["case_id"] == case_id]
    if not matching:
        print(f"No results found for case '{case_id}'")
        return

    print()
    print(bold(f"  Case: {case_id}"))
    print(dim("  " + "─" * 80))

    for r in matching:
        outcome = r["outcome"]
        badge   = outcome_badge(outcome)
        print(f"\n  Repeat {r['repeat']}  {badge}  {r['llm_calls']} calls  {r['wall_s']:.1f}s")

        g = r["graph"]
        print(f"  Nodes: {g['n_nodes']}  Attempts: {g['n_attempts']}")

        laws = g.get("law_proposed", {})
        if laws:
            law_str = "  ".join(f"{col(k, CYAN)}: {v}" for k, v in laws.items())
            print(f"  Laws proposed:  {law_str}")

        acc = g.get("law_accepted", {})
        if acc:
            acc_str = "  ".join(f"{col(k, GREEN)}: {v}" for k, v in acc.items())
            print(f"  Laws accepted:  {acc_str}")

        if r.get("program"):
            print(f"  {col('Program:', GREEN)} {r['program']}")

        # show first 3 unique errors
        errs = list(dict.fromkeys(
            e.split("\n")[0][:80] for e in g.get("error_messages", [])
            if "budget" not in e.lower()
        ))[:3]
        if errs:
            print(f"  {col('Top errors:', YELLOW)}")
            for e in errs:
                print(f"    {dim(e)}")

        # show last 3 raw LLM responses
        raw = r.get("raw_responses", [])
        if raw:
            print(f"  {col('Last LLM responses:', DIM)}")
            for resp in raw[-3:]:
                compact = " ".join(resp.split())[:100]
                print(f"    {dim(compact)}")

    print()

# ── Operator fix hint ──────────────────────────────────────────────────────────
def print_fix_hint(rows):
    """Show how many failures are purely due to operator escaping."""
    total = len(rows)
    op_fail = sum(
        1 for r in rows
        if any("&&" in e or "∧" in e or "'and'" in e
               for e in r["graph"].get("error_messages", []))
           and r["outcome"] != "SUCCESS"
    )
    print()
    print(bold("  Quick fix estimate"))
    print(dim("  " + "─" * 50))
    print(f"  Total runs:               {total}")
    print(f"  Operator-error failures:  {col(str(op_fail), YELLOW)}")
    pct = 100 * op_fail / total if total else 0
    print(f"  As % of all runs:         {pct:.1f}%")
    print()
    print(dim("  Normalising && → /\\, ∧ → /\\, 'and' → /\\ in parse_expr()"))
    print(dim("  could recover these without any model changes."))
    print()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Refine4LLM benchmark viewer")
    ap.add_argument("file",   nargs="?",   help="JSONL result file (default: newest in results/)")
    ap.add_argument("--errors", action="store_true", help="Show error breakdown")
    ap.add_argument("--case",   metavar="ID",        help="Drilldown into one case")
    ap.add_argument("--hint",   action="store_true", help="Show operator-fix estimate")
    args = ap.parse_args()

    path = pick_file(args.file)
    print(col(f"\n  Loading {path.name}  ({path.stat().st_size // 1024} KB)", DIM))
    rows = load(path)
    print(col(f"  {len(rows)} runs loaded", DIM))

    if args.case:
        print_case(rows, args.case)
    elif args.errors:
        print_errors(rows)
    elif args.hint:
        print_fix_hint(rows)
    else:
        print_summary(rows)
        print_fix_hint(rows)

if __name__ == "__main__":
    main()
