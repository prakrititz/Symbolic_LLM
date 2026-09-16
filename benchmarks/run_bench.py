"""Run the FormalLLM refinement benchmark across model configurations."""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.cases import CASES
from benchmarks.harness import run_trial
from benchmarks.oracle import OracleProvider
from FormalLLM.llm.provider import OllamaProvider

CONFIGS = {
    "oracle": dict(kind="oracle"),
    "llama3.1": dict(kind="ollama", model="llama3.1:latest", think=None),
    "qwen3.5-nothink": dict(kind="ollama", model="qwen3.5:latest", think=False),
    "qwen3.5-think": dict(kind="ollama", model="qwen3.5:latest", think=True),
    "ornith": dict(kind="ollama", model="ornith:9b", think=None),
    "ornith-think": dict(kind="ollama", model="ornith:9b", think=True),
    # Same model as llama3.1, run with a larger per-trial call budget (see --budget).
    "llama3.1-wide": dict(kind="ollama", model="llama3.1:latest", think=None),
}


def make_provider(cfg, temperature):
    if cfg["kind"] == "oracle":
        return OracleProvider()
    return OllamaProvider(
        model_name=cfg["model"],
        think=cfg["think"],
        options={"temperature": temperature, "num_predict": 512},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    ap.add_argument("--cases", nargs="+", default=None)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-retries", type=int, default=4)
    ap.add_argument("--budget", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--out", default="benchmarks/results/results.jsonl")
    args = ap.parse_args()

    cases = [c for c in CASES if args.cases is None or c["id"] in args.cases]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    started = time.time()

    with open(args.out, "a", encoding="utf-8") as fh:
        for cfg_name in args.configs:
            cfg = CONFIGS[cfg_name]
            repeats = 1 if cfg["kind"] == "oracle" else args.repeats
            for case in cases:
                for r in range(repeats):
                    provider = make_provider(cfg, args.temperature)
                    rec = run_trial(case, provider, r, cfg_name,
                                    max_retries=args.max_retries, budget=args.budget)
                    if cfg["kind"] == "oracle":
                        rec["oracle_unmatched"] = getattr(provider, "unmatched", [])
                    rec["temperature"] = args.temperature
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"[{time.time()-started:7.1f}s] {cfg_name:16s} {case['id']:20s} "
                          f"r{r} -> {rec['outcome']:9s} calls={rec['llm_calls']:3d} "
                          f"wall={rec['wall_s']:6.1f}s", flush=True)
    print(f"\nDone in {time.time()-started:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
