"""Pre-flight check for the hosted high-end models.

These models are loaded on demand: the first call to a cold model takes minutes
(163s measured for a two-token reply) and the connection is often dropped before
the model ever answers. Once warm, the same call takes ~1.2s. Streaming does not
help here -- the stall is the load itself, and both streaming and non-streaming
requests die during it -- so the fix is to warm the model first, not to change
the request shape.

A benchmark launched against a cold model spends its whole call budget on
transport failures and records them as model failures.

Run this first. It loads each model with a trivial prompt, reports the cold and
warm latency, and checks that a refinement-shaped prompt comes back as parseable
JSON naming a real law.

    FORMALLLM_REMOTE_AUTH='user:password' python benchmarks/check_remote.py

The server holds one model resident at a time, so a request for a second model
evicts the first and blocks behind its load. Checking both models therefore
pays the cold-load cost twice, and interleaving two models during a benchmark
would reload on every call. `run_bench.py` iterates model-major (all cases for
one config, then the next), which keeps a single model resident per arm; keep
it that way, and avoid running a second client against the endpoint at the same
time.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.run_bench import CONFIGS, CONFIG_GROUPS, REMOTE_BASE_URL
from FormalLLM.llm.provider import OpenAIChatProvider
from FormalLLM.llm.parser import parse_llm_response

PROBE = """You are a formal refinement agent. Select a refinement law to apply.

Specification:
Precondition: (N:int) := (N >= 0)
Postcondition: (N:int) := (x = (N + 1))

Available Laws:
- "assignment": parameters {"variable": "x", "expr": "E"} -- refines to x := E.
- "skip": no parameters -- valid only when P already implies Q.

Respond ONLY with valid JSON of the form {"law": "<name>", "parameters": {...}}.
Do not include markdown formatting or explanations."""


def check(name, cfg, timeout, stream):
    provider = OpenAIChatProvider(
        model_name=cfg["model"], base_url=REMOTE_BASE_URL,
        timeout=timeout, stream=stream,
    )
    print(f"\n=== {name}  ({cfg['model']}) ===")

    print("  [1/2] warming up (a cold load can take several minutes) ...", flush=True)
    t0 = time.time()
    try:
        provider.generate("Reply with the single word: ok")
    except Exception as e:
        print(f"  FAILED during warm-up after {time.time() - t0:.0f}s: {e}")
        return False
    cold = time.time() - t0
    print(f"        cold call: {cold:.0f}s")

    print("  [2/2] refinement-shaped prompt ...", flush=True)
    t0 = time.time()
    try:
        text = provider.generate(PROBE)
    except Exception as e:
        print(f"  FAILED after {time.time() - t0:.0f}s: {e}")
        return False
    warm = time.time() - t0

    meta = provider.last_meta
    print(f"        warm call: {warm:.0f}s  "
          f"tokens in/out={meta.get('prompt_eval_count')}/{meta.get('eval_count')}  "
          f"reasoning_channel={meta.get('used_thinking_channel')}  "
          f"finish={meta.get('finish_reason')}")

    if not text.strip():
        print("  FAILED: empty response (no content and no reasoning channel)")
        return False

    try:
        law, params = parse_llm_response(text)
    except Exception as e:
        print(f"  FAILED to parse: {e}\n        raw: {text[:300]!r}")
        return False

    print(f"        parsed law={law!r} params={ {k: str(v) for k, v in params.items()} }")
    # A budget note the caller can act on: 30 calls is the default per trial.
    print(f"        => ~{warm * 30 / 60:.0f} min per trial at the default 30-call budget")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=CONFIG_GROUPS["high-end"])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--no-stream", action="store_true",
                    help="disable SSE streaming (both modes work once the model "
                         "is warm; neither survives a cold load)")
    args = ap.parse_args()

    if not os.environ.get("FORMALLLM_REMOTE_AUTH"):
        print("FORMALLLM_REMOTE_AUTH is not set; expected 'user:password'.")
        return 2

    print(f"endpoint: {REMOTE_BASE_URL}")
    ok = True
    for name in args.configs:
        cfg = CONFIGS[name]
        if cfg.get("kind") != "openai":
            print(f"\n=== {name} === skipped (not a hosted model)")
            continue
        ok &= check(name, cfg, args.timeout, not args.no_stream)

    print("\nall hosted models reachable and answering in the expected format"
          if ok else "\nsome checks failed (see above)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
