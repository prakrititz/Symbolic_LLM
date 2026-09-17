"""Run the FormalLLM refinement benchmark across model configurations."""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.cases import CASES
from benchmarks.harness import run_trial
from FormalLLM.llm.provider import OllamaProvider, OpenAIChatProvider

CORE_LAWS = ["assignment", "skip", "sequential", "alternation", "iteration"]
EXTENDED_LAWS = CORE_LAWS + ["strengthen_post", "weaken_pre",
                             "initialized_skip", "flexible_sequential"]
LAW_SETS = {"core": CORE_LAWS, "extended": EXTENDED_LAWS, "all": None}

# Hosted OpenAI-compatible endpoint serving the large models. Credentials are
# NOT stored here -- OpenAIChatProvider reads FORMALLLM_REMOTE_AUTH from the
# environment, so the endpoint's password never enters the repo or a results
# file. Override the host with FORMALLLM_REMOTE_URL.
REMOTE_BASE_URL = os.environ.get(
    "FORMALLLM_REMOTE_URL",
    "https://broodless-alethia-nipping.ngrok-free.dev/v1",
)

# NOTE: there is deliberately no "oracle" configuration here.
# It used to replay a hand-written playbook of correct moves and was reported
# alongside the models as though it were a result. It is not one: it measures
# whether the playbook's author can write a correct refinement, and every entry
# in it was added by hand for the case it solves. Quoting it as "the engine
# reaches 10/12" invites exactly the confusion it caused. The scripted
# refinements now live in FormalLLM/tests/test_engine_reachability.py, where
# they are what they always were -- regression tests that the engine accepts a
# known-good refinement -- and never appear in a results table.
CONFIGS = {
    "llama3.1": dict(kind="ollama", model="llama3.1:latest", think=None),
    "qwen3.5-nothink": dict(kind="ollama", model="qwen3.5:latest", think=False),
    "qwen3.5-think": dict(kind="ollama", model="qwen3.5:latest", think=True),
    "ornith": dict(kind="ollama", model="ornith:9b", think=None),
    "ornith-think": dict(kind="ollama", model="ornith:9b", think=True),
    # Same model as llama3.1, run with a larger per-trial call budget (see --budget).
    "llama3.1-wide": dict(kind="ollama", model="llama3.1:latest", think=None),

    # --- high-end arm -----------------------------------------------------
    # Hosted models an order of magnitude larger than the local 8-10B arms.
    # Study 1 left law selection and parameter synthesis confounded with model
    # capacity: every local model failed Tier B, so we could not tell a hard
    # case from a weak guide. These arms separate the two.
    "gpt-oss-120b": dict(kind="openai", model="gpt-oss:120b"),
    "qwen3-coder-next": dict(kind="openai", model="qwen3-coder-next:latest"),
}

#: Named groups so an arm can be selected without listing every config.
#: `--configs high-end` expands to the hosted models, `local` to the Ollama ones.
CONFIG_GROUPS = {
    "high-end": ["gpt-oss-120b", "qwen3-coder-next"],
    "local": ["llama3.1", "qwen3.5-nothink", "qwen3.5-think", "ornith", "ornith-think"],
    "all": [name for name in CONFIGS],
}


def expand_configs(names):
    """Expand any group names in `names`, preserving order and dropping repeats."""
    out = []
    for name in names:
        for resolved in CONFIG_GROUPS.get(name, [name]):
            if resolved not in out:
                out.append(resolved)
    unknown = [n for n in out if n not in CONFIGS]
    if unknown:
        raise SystemExit(
            f"unknown config(s) {unknown}; known configs are {sorted(CONFIGS)} "
            f"and groups {sorted(CONFIG_GROUPS)}"
        )
    return out


def make_provider(cfg, temperature, timeout=900):
    if cfg["kind"] == "openai":
        return OpenAIChatProvider(
            model_name=cfg["model"],
            base_url=REMOTE_BASE_URL,
            temperature=temperature,
            # Reasoning models spend hundreds of tokens thinking before the
            # answer; at 512 gpt-oss returned no content at all and only its
            # reasoning channel, which is prose rather than the JSON we need.
            max_tokens=cfg.get("max_tokens", 2048),
            # A hosted 120B behind a tunnel answers in tens of seconds, and far
            # longer on a cold load, so the per-call timeout is generous. The
            # per-trial call budget still bounds the total.
            timeout=timeout,
        )
    return OllamaProvider(
        model_name=cfg["model"],
        think=cfg["think"],
        # num_ctx matters for memory, not just quality: these models advertise a
        # 128k+ context and Ollama sizes the KV cache to it, which pushed the
        # server past 12 GB resident and got runs OOM-killed. Our prompts are
        # ~1-2k tokens, so 4096 is ample.
        options={"temperature": temperature, "num_predict": 512,
                 "num_ctx": 4096},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS),
                    help="config names, or a group: "
                         + ", ".join(sorted(CONFIG_GROUPS)))
    ap.add_argument("--cases", nargs="+", default=None)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-retries", type=int, default=4)
    ap.add_argument("--budget", type=int, default=30)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--timeout", type=int, default=900,
                    help="per-call timeout in seconds for hosted models")
    ap.add_argument("--laws", choices=sorted(LAW_SETS), default="all",
                    help="restrict the engine to a law set so that the law set "
                         "is the only variable between arms")
    ap.add_argument("--out", default="benchmarks/results/results.jsonl")
    args = ap.parse_args()

    config_names = expand_configs(args.configs)
    cases = [c for c in CASES if args.cases is None or c["id"] in args.cases]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    started = time.time()

    with open(args.out, "a", encoding="utf-8") as fh:
        for cfg_name in config_names:
            cfg = CONFIGS[cfg_name]
            repeats = args.repeats
            for case in cases:
                for r in range(repeats):
                    provider = make_provider(cfg, args.temperature, args.timeout)
                    rec = run_trial(case, provider, r, cfg_name,
                                    max_retries=args.max_retries,
                                    budget=args.budget,
                                    law_set=LAW_SETS[args.laws],
                                    max_depth=args.max_depth)
                    rec["temperature"] = args.temperature
                    rec["law_arm"] = args.laws
                    rec["model"] = cfg.get("model")
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"[{time.time()-started:7.1f}s] {args.laws:8s} {cfg_name:16s} {case['id']:20s} "
                          f"r{r} -> {rec['outcome']:9s} calls={rec['llm_calls']:3d} "
                          f"wall={rec['wall_s']:6.1f}s", flush=True)
    print(f"\nDone in {time.time()-started:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
