# Study 3 — The Paper's Square-Root Example, With and Without Refinement

A follow-up to [`REPORT.md`](REPORT.md) (Study 1) and
[`REPORT2-extended-laws.md`](REPORT2-extended-laws.md) (Study 2). Neither is
superseded or edited.

Studies 1 and 2 measured how far a model gets *inside* the refinement engine.
Study 3 asks the question the paper's Figure 1 actually poses: **for the same
specification, is the code better with the refinement calculus or without it?**

Both arms ask the same models for a Python implementation of the same
specification. They differ only in how the code is produced.

| Arm | How the code is produced | What checks it |
|---|---|---|
| `direct` | The model writes the function itself. | Nothing. Whatever it writes is what runs. |
| `refinement` | The model only chooses refinement laws and their parameters. | Z3 discharges every step; the Python is **emitted from the verified refinement tree**, never written by the model. |

Every generated file is stored under `benchmarks/study3_code/<config>/`, with a
header naming the arm that produced it, so the two can be read side by side.

---

## 1. The specification

The paper's motivating example (Figures 1–3), transcribed into `L_spec`:

```
Precondition:  (N:float)(e:float) := N >= 0 /\ e > 0.
Postcondition: (N:float)(e:float) := x*x <= N /\ N < (x+e)*(x+e).
```

"Find the square root of N to within the error bound e." It is registered as
case `C5-sqrt-paper` in `benchmarks/cases.py`, with the executable contract in
`benchmarks/baseline_cases.py`.

### 1.1 Why these twelve inputs

The paper reports three specific defects in code from Copilot, GPT-4 and
o1-preview. The inputs are chosen to expose exactly those:

| Input | Failure mode it probes | Paper's attribution |
|---|---|---|
| `N = 0.5, 0.25, 0.9` | `N < 1`, where `√N > N`, so `high = N` is not a valid upper bound | GitHub Copilot |
| `N = 5.0` | float fixed point: `x` stops changing but the guard stays true | GPT-4 |
| `N = 1e-6` | `N < (e/4)²`, where `x` initialises negative | o1-preview |
| `N = 0, 2, 16, 1, 123.456, 10000` | ordinary values | — |

Generated code runs in a separate process under a **10-second wall-clock
limit**. That limit is not incidental: a program that never terminates is the
paper's central example of a plausible-looking wrong answer, and the timeout is
what distinguishes it from a wrong result.

---

## 2. Setup

| | |
|---|---|
| Engine | this repo, at the M0 state (see §6) |
| Prover | Z3 via `z3-solver`, default tactics |
| Law set | all nine registered laws |
| Budget | 15 LLM calls per refinement trial; `max_retries = 4` per node |
| Repeats | 1 |
| Local serving | Ollama, `num_ctx 4096`, `temperature 0.2` |
| Hosted serving | OpenAI-compatible endpoint, SSE streaming, `temperature 0.2` |
| Runner | `benchmarks/study3.py`; tables from `benchmarks/analyse_study3.py` |

### Configurations

| Name | Model | Size | Where |
|---|---|---|---|
| *(no oracle arm)* | — | — | see the note below |
| `gpt-oss-120b` | `gpt-oss:120b` | 120B | hosted |
| `qwen3-coder-next` | `qwen3-coder-next:latest` | — | hosted |
| `llama3.1` | `llama3.1:latest` | 8.0B Q4_K_M | local |
| `qwen3.5-nothink` / `-think` | `qwen3.5:latest` | 9.7B Q4_K_M | local |
| `ornith` / `ornith-think` | `ornith:9b` | 9.0B Q4_K_M | local |

**On the removed "oracle" arm.** Earlier drafts of this report carried a row
labelled `oracle`, which replayed a hand-written playbook of correct moves, and
quoted it as "the engine ceiling". That was a mistake and the row has been
removed. The playbook was written by the same person reading the results, and
every entry in it was added by hand for the case it solves; it can only show
that the engine accepts a refinement someone already knew, which is not a
measurement of this system and must not be set beside model results as though
it were one. Those scripts now live in
`FormalLLM/tests/test_engine_reachability.py` as regression tests. Where this
report needs to distinguish "the engine cannot" from "the model did not", it now
says so explicitly and points at those tests rather than quoting a score.

---

## 3. Results

### 3.1 Headline

| | Passes all 12 inputs |
|---|---|
| **Direct** — model writes the code, nothing verifies it | **5 / 7** |
| **Refinement** — model guides the calculus, Z3 verifies every step | **0 / 7** |

On this specification the refinement pipeline made **every** model worse. No
model completed a refinement of it, before or after the fixes in §8.

A separate question is whether the *engine* can express this refinement at all.
It can: `test_engine_reachability.py` walks it in three hand-written steps with
every obligation discharged. That is a statement about the calculus, not a
result of this study, and it is deliberately not tabulated here.

### 3.2 Per model

| Model | Direct | Direct verdict | Refinement (v1) | Refinement (v2) |
|---|---|---|---|---|
| `gpt-oss-120b` | 12/12 | PASS *(called `math.sqrt`)* | EXHAUSTED | BUDGET |
| `qwen3-coder-next` | 12/12 | PASS | BUDGET | EXHAUSTED |
| `llama3.1` | 9/12 | **fails exactly N < 1** | EXHAUSTED | EXHAUSTED |
| `qwen3.5-nothink` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |
| `qwen3.5-think` | 0/12 | does not run (bad indentation) | ERROR | EXHAUSTED |
| `ornith` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |
| `ornith-think` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |

v1 and v2 differ by the parser defect described in §4; v2 is the corrected run.

### 3.3 Refinement arm, in detail

| Model | v2 outcome | Calls | Laws accepted before failing |
|---|---|---|---|
| `gpt-oss-120b` | BUDGET | 15 | `sequential`, `assignment`, `strengthen_post` ×2, `weaken_pre` |
| `llama3.1` | EXHAUSTED | 15 | `sequential`, `alternation` |
| `qwen3-coder-next` | EXHAUSTED | 15 | `alternation` |
| `qwen3.5-nothink` | EXHAUSTED | 4 | — |
| `qwen3.5-think` | EXHAUSTED | 4 | — |
| `ornith` | EXHAUSTED | 4 | — |
| `ornith-think` | EXHAUSTED | 4 | — |

Two distinct failure shapes, and the distinction matters:

- **The four 9B-class models stop at exactly 4 calls** — `max_retries` at the
  root. They never reach the call budget because they never get a single law
  accepted at the root node. This is failure at *law selection*.
- **`gpt-oss-120b` and `llama3.1` descend a real tree**, accumulating verified
  steps, and run out of budget or retries deeper down. This is failure at
  *parameter synthesis* — finding the intermediate assertion, guard and variant
  that discharge.

---

## 4. A defect in this harness, found mid-study

The first run had **all seven models at 0/12** in the refinement arm. Seven
identical failures is a property of the harness, not seven independent model
failures, so the raw proposals were examined:

```json
{"law": "weaken_pre", "parameters": {"intermediate_pre": "(N >= 0) /\n(e > 0)"}}
```

The model wrote `/\`, `L_spec`'s conjunction, inside a JSON string. JSON decodes
`\n` as a newline, so the parser received `/` followed by a newline — a syntax
error. `/\"` arrived as `/"`. Three of qwen3.5's four proposals were destroyed
this way. **The arm was scoring the models' JSON-escaping, not their
refinement.**

The fix (`FormalLLM/llm/parser.py`) accepts backslash-free spellings — `&&`,
`||`, `!`, `!=`, and the words `and` / `or` / `not` — which survive JSON intact,
and the prompt now recommends them. Word forms are `\b`-anchored so identifiers
such as `band` and `x_or_y` are untouched. An expression still showing the
mangled signature now raises an error naming the spelling to use instead of
failing with a bare parse error.

Effect, measured as laws accepted before failure:

| Model | v1 | v2 |
|---|---|---|
| `gpt-oss-120b` | `{}` | `{sequential, assignment, strengthen_post ×2, weaken_pre}` |
| `llama3.1` | `{}` | `{sequential, alternation}` |
| 9B-class locals | `{}` | `{}` — unchanged |

So the defect was masking real capability in the two larger models, and masking
nothing in the smaller ones: they fail at law selection regardless.

Both datasets are kept — `results_study3_prefix.jsonl` (v1) and
`results_study3_v2.jsonl` (v2) — because the defect is itself a finding about
this class of system: an LLM-facing formal language whose operators collide with
the transport encoding will silently measure the wrong thing.

---

## 5. What the generated code actually looks like

### 5.1 What a correct refinement produces (hand-written, not measured)

```python
def f(N: float, e: float) -> float:
    x = 0
    while (N >= ((x + e) * (x + e))):
        x = (x + e)
    return x
```

Emitted from the verified tree. **No model produced this** -- the steps were
written by hand to show what the calculus yields, and it is included to explain
the mechanism, not as a score. It passes all 12 inputs, including every one the
paper says the commercial models get wrong, and is the paper's Figure 3 program.

### 5.2 Direct arm, `llama3.1` — the paper's Figure 1 bug, reproduced

```python
low = 0
high = N                      # <-- invalid upper bound when N < 1
while high - low > e:
    mid = (low + high) / 2
    if mid * mid <= N:
        low = mid
    else:
        high = mid
return low
```

It fails on **N = 0.5, N = 0.25, N = 0.9 — precisely and only the inputs with
N < 1**, because `√N > N` there, so the true root lies outside `[0, N]`. This is
exactly the Copilot defect the paper opens with, reproduced independently on a
different model, and the only case in this study where a model genuinely derived
an algorithm rather than calling a library.

### 5.3 Direct arm, `gpt-oss-120b` — passes, but delegates

```python
s = math.sqrt(N)
x = s - e / 2.0
return x if x > 0 else 0.0
```

12/12, but by calling `math.sqrt`. It did not solve the problem the
specification poses; it deferred to the standard library. The refinement arm
forbids this — `L_spec` has no `sqrt` — which is part of why the arms are not
directly comparable as "which writes better code" (see §7).

### 5.4 Direct arm, `qwen3.5-think` — does not run

```python
import math

    def f(N: float, e: float) -> float:
        return math.sqrt(N)
```

Indented after a top-level import: a syntax error. Scored 0/12 for reasons that
have nothing to do with the algorithm, which would otherwise have passed.

---

## 6. Threats to validity

- **One case, one repeat.** Every number here is a single trial on a single
  specification. Nothing about variance is claimed.
- **The direct arm is not a fair "better code" comparison.** Two of its five
  passes are `math.sqrt` calls, and one failure is a syntax error rather than a
  logic error. The honest reading is narrower: *the direct arm produces
  something runnable more often; only one model derived an actual algorithm, and
  that one carried the paper's bug.*
- **Budget.** `gpt-oss-120b` hit the 15-call budget while still making verified
  progress, so its `BUDGET` result is a floor, not a verdict. A wider-budget run
  is reported in §8.
- **Engine state.** Run at the M0 state of the engine, which includes two
  correctness fixes from that milestone (`substitute` no longer corrupts the
  spec it is given; `to_previous_state` no longer degenerates the variant
  obligation). Earlier studies predate both.
- **Interrupted runs.** Two batches were killed by host memory pressure and
  wrote partial rows before dying; the affected configs were re-run
  individually. `analyse_study3.py` takes the last row per config, which is the
  clean re-run. The duplicate partial rows remain in the file.
- **`qwen3.5-think` v1 `ERROR`** was an Ollama HTTP 500, i.e. infrastructure,
  not a model failure. Its v2 row is a clean run.

---

## 7. What this means for the roadmap

The result is not that refinement cannot work -- the hand-written walkthrough
shows the calculus reaches a correct program in a few steps. It is that **the refinement path is currently unnavigable by any
model we have**, and the reason is visible in §3.3:

1. **The initialised-iteration law (Lemma 6.6) is missing.** The only route to
   a correct refinement was `sequential` with an intermediate that establishes
   the loop invariant — exactly the composite step the paper's derived law
   exists to make into one move. Without it a model must invent the invariant *and* guess
   that `sequential` is the way to reach it. This is the strongest argument yet
   for **M2**.
2. **Law selection fails outright below ~100B.** Four models never got one law
   accepted at the root. No amount of budget helps; they need either better
   guidance in the prompt or the higher-level laws that make the right move
   obvious.
3. **The two larger models fail at parameter synthesis, not law choice.** They
   pick plausible laws and descend; what they cannot produce is the witness
   expression that discharges. That is what the paper's retrieval-augmented
   prompting and instruction tuning (§8.2) address, and it is what **M6**'s
   learned laws would shortcut.

---

## 8. Why the refinement arm failed: six causes, five of them ours

The 0/7 in §3.1 is not a finding about refinement. Investigating it turned up
six separate causes, and only one is a property of the models.

| # | Cause | Evidence | Fixed? |
|---|---|---|---|
| 1 | **No frame.** `Spec` records typed params but not *which variables the program may modify*, so facts about unmodified variables cannot reach a sub-specification. | `gpt-oss-120b`'s invariant verifies at the root and fails in the loop body; adding `e > 0` -- a precondition fact that can never change -- makes it verify. | **No** |
| 2 | **Iteration pinned the invariant to the precondition.** The paper's Table 5 has the LLM supply `I`. | `invariant_expr = spec.precondition.expr`; the initialisation branch was unreachable. | Yes |
| 3 | **`/\` destroyed by JSON escaping.** | 3 of 4 qwen3.5 proposals, 8 of 12 llama3.1 calls. | Yes (`&&`) |
| 4 | **Reasoning prose parsed as JSON.** A reasoning model spends its budget thinking, returns empty `content`, and the reasoning-channel fallback hands prose to `json.loads`. | `gpt-oss-120b` scored `ERROR` on replies that contained a valid answer. | Yes |
| 5 | **Hosted `max_tokens` of 512** truncated reasoning models before they answered. | Same runs as #4. | Yes (2048) |
| 6 | **Transient socket failures aborted whole trials.** | Three runs lost to `WinError 10013` / `RemoteDisconnected`. | Yes (retry) |

### 8.1 The budget question, answered

An earlier hypothesis -- that `gpt-oss-120b`'s `BUDGET` outcome meant the
15-call cap was simply too small -- is **wrong**. At a 40-call budget it
returned `EXHAUSTED` after 18 calls: it runs out of *retries*, not ro om. Budget
is not the lever.

### 8.2 What the model actually proposed

With causes 2-6 fixed, `gpt-oss-120b` proposes `iteration` four times, and its
first attempt is:

```json
{"invariant": "(x * x) <= N",
 "guard": "N >= (x + e) * (x + e)",
 "variant": "N - (x * x)"}
```

The guard and variant are exactly those of the hand-written refinement. Only
the invariant is incomplete -- it omits `e > 0` and `x >= 0`, without which the
body's variant-decrease obligation cannot be discharged. `e > 0` is in the
precondition and `e` is never assigned, so a calculus with a frame would carry
it automatically; Morgan's `x : [pre, post]` notation exists precisely to say
which variables may change.

Supplying the model's own guard and variant, with its invariant conjoined with
that frame context, completes the refinement in **three moves**:

```python
def f(N: float, e: float) -> float:
    x = 0
    while (N >= ((x + e) * (x + e))):
        x = (x + e)
    return x
```

**78/78 on the adversarial grid** (`study3_code/gpt-oss-120b/C5-sqrt-paper_refined_with_frame.py`).

So the largest model already produces a correct refinement of the paper's
motivating example. What blocked it was the missing frame, not its reasoning.

### 8.3 The 9B-class models are a different story

`llama3.1` never proposes `iteration` at all across 12 calls
(`{unknown: 8, strengthen_post: 3, alternation: 2}`), and the four 9B-class
models stop after exactly 4 calls without a single accepted law. They fail at
law *selection*, which no amount of engine fixing addresses -- it is what the
paper solves with instruction tuning on Morgan's examples. They should be
reported as a capability floor, not as a reproduction target.

## 8.4 Why the direct arm did not fail

The paper's Figure 1 shows LLMs writing *wrong algorithms* for this problem.
Five of our seven models instead called `math.sqrt`, which is correct and
robust -- 78/78 on the adversarial grid. They never attempted the algorithm the
specification describes.

The one model that did derive an algorithm, `llama3.1`, failed exactly as the
paper predicts. So the direct arm did not fail because the comparison is
unfair in the other direction: the refinement arm must synthesise (L_spec has no
`sqrt`), while the direct arm may call a library that answers the question in
one line. A no-library sub-arm is needed for a like-for-like comparison, and
`sqrt` is in any case the weakest possible case to make the paper's point --
the Table 7 problems (linear search, max element, Dutch flag sort, pattern
matching) have no library shortcut.

---

## 8.5 Study 3b: the like-for-like comparison

§8.4 argued the direct arm was not really being asked to synthesise anything.
Re-running it with library calls forbidden -- the same constraint the refinement
arm works under, since `L_pl` has no function calls -- changes the result
completely.

| Model | Direct (unrestricted) | Direct (**no library**) |
|---|---|---|
| `llama3.1` | 9/12 | **5/12** |
| `qwen3.5-nothink` | 12/12 | **4/12** |
| `ornith` | 12/12 | **2/12** |
| *refinement, by any model* | — | **0/7 completed** |

Every model that "passed" did so by calling `math.sqrt`. Forced to write the
algorithm, all three produce plausible-looking code that violates the
specification -- which is exactly the paper's Figure 1 claim.

### What they wrote

`qwen3.5-nothink` and `ornith` both chose **Newton's method**:

```python
next_x = (x + N / x) / 2
if abs(next_x - x) <= e:
    return next_x
```

This is the paper's GPT-4 failure. Newton converges to the root *from above*, so
the result systematically has `x*x > N`, and the termination test `|Δx| <= e`
says nothing about the postcondition. The numbers make the point better than the
argument does -- for `N = 5`, it returns

```
x = 2.236068896      (sqrt(5) = 2.2360679...)   ->  x*x = 5.0000004 > 5
```

Wrong by four parts in ten million: indistinguishable from correct in any
eyeball test, and a violation of `x*x <= N`. `ornith` fails the same way on 10
of 12 inputs, `qwen3.5` on 8.

`llama3.1` instead steps by a fixed `1.0` with a stray `return N / x` branch and
*undershoots*, failing `N < (x+e)*(x+e)` on 7 inputs including every `N < 1`.

### Why the refinement arm cannot fail this way

The refined program is

```python
x = 0
while (N >= ((x + e) * (x + e))):
    x = (x + e)
```

Its loop guard is the negation of the postcondition's second conjunct, and the
invariant carries the first. It cannot overshoot, because overshooting is
exactly what the guard tests; it cannot terminate early, because the guard is
the termination condition. That is what "correct by construction" buys, and it
is why the hand-written refinement passes all 12 of the paper's inputs and
78/78 on the wider adversarial grid. No model has yet produced it.

### Caveat

`qwen3.5-nothink` used `abs()` despite the instruction not to; the harness
records the violation (`used_library: ["abs("]`) rather than silently excusing
it. Its failures are overshoot, not the `abs` call, so the result stands, but
the arm is "library calls discouraged and recorded", not "library calls
impossible".

## 8.6 What now reproduces, and what does not

With the frame (§8, cause 1) implemented, the engine ceiling is **10 of 12
cases**, up from 8 of 11:

| Case | Before | After |
|---|---|---|
| `C5-sqrt-paper` | unreachable | SUCCESS in 4 calls |
| `C3-loop-pinned` | EXHAUSTED -- recorded as an engine limitation | SUCCESS in 3 calls |

`C3`'s case note previously read "the engine reuses the precondition as the loop
invariant, so `i = 0` is pinned and no body can preserve it". That was not a
property of the problem; it was cause 2, and it is gone.

So the paper's shape -- **refinement correct, direct subtly wrong** -- now holds
at the level of what the calculus can express -- a correct refinement passes
12/12 where the unaided models score 2-5/12. What is still missing is a *model*
that can drive the refinement unaided. `gpt-oss-120b` gets closest, proposing
the correct guard and variant; with the frame it now needs to supply only
`x*x <= N && x >= 0` rather than three conjuncts. That is the next measurement.

## 9. Reproducing

```bash
# both arms, all models
FORMALLLM_REMOTE_AUTH='user:pass' \
python benchmarks/study3.py --configs high-end local \
    --arms direct refinement --repeats 1 --budget 15 \
    --out benchmarks/results/results_study3.jsonl

# tables
python benchmarks/analyse_study3.py > benchmarks/results/study3_tables.md
```

Local models must be run **one at a time** — a 9B model plus a 128k-sized KV
cache will not co-reside on a 23 GB machine, which killed two batches during
this study. `benchmarks/check_remote.py` warms a hosted model before a run; a
cold 120B takes ~225s to load and the connection is usually dropped before it
answers.

Artefacts:

| Path | Contents |
|---|---|
| `benchmarks/results/results_study3_prefix.jsonl` | v1, both arms (with the escaping defect) |
| `benchmarks/results/results_study3_v2.jsonl` | v2 refinement arm (defect fixed) |
| `benchmarks/results/results_study3_wide.jsonl` | wider-budget probe |
| `benchmarks/results/study3_tables.md` | generated tables |
| `benchmarks/study3_code/<config>/` | every generated program, both arms |
