# Study 2 — Do the Extended Refinement Laws Help?

A follow-up to [`REPORT.md`](REPORT.md) (Study 1). **Study 1 is not superseded and
has not been edited**; its numbers stand for the engine and harness as they were
at commit `6301384` plus the five defect fixes described in its §3.

Study 1 ended with a specific, testable hypothesis:

> This implementation's `sequential` law needs an intermediate `R` that works
> verbatim on both halves, whereas the paper's Flexible Sequential Composition
> (Lemma 6.2) only needs `P => A`, `B => C`, `D => Q` — a far larger target to
> hit. That gap is the likeliest single explanation for the Tier-B wipeout.

Study 2 tests exactly that: the same models, cases, budget and prompt, with the
**law set as the only variable**.

---

## 1. Why the two studies' numbers must not be compared directly

Between Study 1 and Study 2 the engine, the prompt and the serving
configuration all changed. Four differences act on the core-law arm
simultaneously, so **a core-arm number here is not a restatement of the same
cell in Study 1**, and any difference between them is uninterpretable.

Study 2's finding is the *within-study* contrast between its own two arms, which
share everything except the registered laws.

### 1.1 Engine changes (author's commits, after Study 1)

| Commit | Change |
|---|---|
| `d8345d5` | Commits Study 1's five defect fixes (iteration wiring, `V = V0`, `Const` previous-state, typed params reaching Z3, thinking-channel fallback) |
| `1299c6d` | Adds four extended laws: `strengthen_post` (Lemma 2.1), `weaken_pre` (2.2), `initialized_skip` (6.1), `flexible_sequential` (6.2); plus `manual_sqrt.py` and deliberate-failure tests |
| `1825032` | L_mix bridging: program nodes render through `to_string`, compact spec form, reconstruction for the new recursive laws |
| `429bdb9` | Wires the four new laws through `llm/parser.py`; `TOTAL_LAWS = len(engine.laws)` |

On `1299c6d`/`1825032` the extended laws were registered in the engine and
advertised in the prompt, but `parse_llm_response` had no branch for them, so
every LLM proposal of one was recorded as an `ERROR`. `429bdb9` fixed that.
Verified end-to-end before this study: a scripted `flexible_sequential` solves
`B1-sequential` in 3 calls through the full LLM path.

`manual_sqrt.py` reproduces the paper's Figure 3 refinement under Z3:

```
x := 0; while N >= (x+e)*(x+e): x := x + e
```

### 1.2 Harness changes made for this study

| Change | Why |
|---|---|
| **Progress guard** in `AutomatedRefiner` | `strengthen_post` with `R = Q` and `weaken_pre` with `R = P` discharge their obligations trivially (`Q => Q`) and regenerate the parent spec verbatim. The refiner recursed into an identical node until the budget died — `A1-skip` went from solved to 30 wasted calls. The guard rejects any step whose sub-spec matches the current node **or any ancestor**. |
| **Depth bound** (`--max-depth 6`) | The guard cannot catch `alternation`: each `P /\ G /\ G' ...` is *syntactically new*, so it is not an ancestor repeat. `alternation` and `sequential` emit no proof obligations, so nothing rejects them and the search descends forever. Past the bound only `assignment` / `skip` are permitted. |
| **Prompt lists only registered laws** | Required for a fair core arm: otherwise it advertises nine laws the engine cannot apply, and every retry spent on one is wasted. |
| **Expression-syntax block in the prompt** | Models kept emitting `&&`, `\|\|`, `sqrt()`, `max()`, `\geq` — none of which L_spec parses. |
| **`--laws core\|extended\|all`** | Filters `engine.laws`, which the refiner reads for *both* `TOTAL_LAWS` and the advertised law list, so one switch controls advertising, parsing and search. |
| **`num_ctx: 4096`** | llama3.1 advertises a 131k context and Ollama sizes the KV cache to match; `llama-server` reached 12 GB resident on a 23 GB machine and three runs were OOM-killed. Prompts here are 1–2k tokens, so nothing is truncated. |
| **One model resident at a time** (`run_lawcmp.sh`) | Explicit `keep_alive: 0` unload between arms, so llama3.1 and qwen3.5 never stack. |

A consequence worth stating plainly: Study 1's `A1-skip` success for llama3.1 was
the ill-typed `x = (x > 0)`, which Z3 accepted only via z3py's silent `Bool -> Int`
coercion (`If(0 < x, 1, 0) > 0`). The syntax block discourages that form, so the
accidental success is expected to disappear here. That is a more honest
measurement, not a regression.

### 1.3 Test-suite change

`test_fallback.py` scripted `sequential` with `intermediate = "N >= 0"` against
`[N >= 0, x*x <= N]`, which produces a second sub-spec **identical to the
parent** — precisely the no-op the progress guard now rejects. The intermediate
was changed to `N > -1`, which is still implied by the precondition (so the
scripted `skip` still succeeds) but genuinely changes the specification,
preserving what the test exercises: fallback when a child cannot be refined.

Four new tests in `test_progress_guard.py` cover the guard directly, including
one asserting it does **not** block a genuine `strengthen_post` (`x > 0` → `x > 3`).

### 1.4 Experimental design

| | Study 1 | Study 2 |
|---|---|---|
| Configurations | 7 (oracle, llama3.1, llama3.1-wide, qwen3.5 ×2, ornith ×2) | 2 models × 2 law arms |
| Repeats | 3 (2 for the wide arm) | 2 |
| Budget | 30 calls (100 for one arm) | 30 calls |
| Depth bound | none | 6 |
| Progress guard | none | yes |
| `num_ctx` | model default (~131k) | 4096 |
| Trials | 187 | 88 |

Two repeats is thin. Study 1 already showed high within-cell variance — in this
run `C1-sqrt-loose` on llama3.1 gave SUCCESS in 1 call on one repeat and a
30-call budget abort on the next, same temperature. **Single-cell differences
between arms are noise; only aggregate and tier-level contrasts are read below.**

---

## 2. Results

88 trials: 2 models x 11 cases x 2 repeats x 2 law arms.

### 2.1 Headline — the hypothesis is refuted

| Tier | core (5 laws) | extended (9 laws) |
|---|---|---|
| A | 10/16 | 5/16 |
| B | **0/12** | **0/12** |
| C | 5/16 | 0/16 |
| **all** | **15/44 (34%)** | **5/44 (11%)** |

Adding the extended laws did not move Tier B off zero, and made overall
performance **three times worse**. Both models regressed:

| Config | core | extended |
|---|---|---|
| llama3.1 | 9/22 (41%) | 2/22 (9%) |
| qwen3.5-nothink | 6/22 (27%) | 3/22 (14%) |

### 2.2 Why: the models never reach for the law the hypothesis rested on

`flexible_sequential` -- Lemma 6.2, the law Study 1 predicted would crack
Tier B -- was proposed **5 times out of 396 calls by llama3.1, and never by
qwen3.5-nothink**.

| Config | New law | Proposed | Accepted | Share of proposals |
|---|---|---|---|---|
| llama3.1 | strengthen_post | **165** | 2 | **38.9%** |
| llama3.1 | flexible_sequential | 5 | 0 | 1.2% |
| llama3.1 | weaken_pre | 0 | 0 | 0.0% |
| llama3.1 | initialized_skip | 0 | 0 | 0.0% |
| qwen3.5-nothink | weaken_pre | 12 | 0 | 14.5% |
| qwen3.5-nothink | strengthen_post | 1 | 0 | 1.2% |
| qwen3.5-nothink | flexible_sequential | 0 | 0 | 0.0% |
| qwen3.5-nothink | initialized_skip | 0 | 0 | 0.0% |

This is not a defect in the law. Driven directly with a scripted
`flexible_sequential`, `B1-sequential` is solved in 3 LLM calls
(`s := A + B ; d := A - B`), all three obligations discharged. The law works.
The models simply do not select it.

What they select instead is `strengthen_post`, which llama3.1 proposed 165
times and had accepted twice. It is the cheapest-looking move in the list --
"just restate the postcondition" -- and the overwhelmingly common instance is
the identity `R = Q`, which the progress guard rejects. Without that guard this
arm would not have produced results at all; with it, the model spends its whole
budget proposing a no-op and being told no.

### 2.3 Format adherence collapses as the law list grows

| Config | Law set | Malformed output | Avg prompt tokens/call |
|---|---|---|---|
| llama3.1 | core | 12/350 (3%) | 445 |
| llama3.1 | extended | 44/396 (11%) | 586 |
| qwen3.5-nothink | core | 15/198 (8%) | 445 |
| qwen3.5-nothink | extended | **50/83 (60%)** | 586 |

qwen3.5-nothink in the extended arm is failing *fast*: 3.8 calls per case, 60%
malformed, zero budget aborts. It is not searching, it is emitting garbage and
exhausting its retries.

A caveat on attribution: offering a law necessarily means describing it, so the
extended arm's prompt is ~140 tokens longer per call. "More laws" and "longer
prompt" cannot be fully separated by this design. The law histogram argues the
effect is mostly about choice, not length -- the models do not use the new laws
even when they parse them correctly -- but the confound is real.

### 2.4 The JSON escaping defect dominates the error log

The most common parse failures in the extended arm are all the same defect
identified in Study 1 section 4:

```
Unexpected token Token('SLASH', '/') at line 1, column 27.   x14
Unexpected token Token('SLASH', '/') at line 1, column 34.   x10
No terminal matches '"' in the current parser context        x3
```

These are `/\` written unescaped inside a JSON string. `flexible_sequential`
needs four connective-heavy expressions per call, which is the worst possible
exposure to this bug -- a plausible reason the models avoid it after one or two
failures, though with 5 proposals total there is not enough data to claim that.

### 2.5 Full detail

Same models, cases, budget (30) and temperature (0.2).

## Per-case: core -> extended

| Case | Tier | llama3.1 | qwen3.5-nothink |
|---|---|---|---|
| A1-skip | A | 0/2 -> 0/2 | 2/2 -> 1/2  down |
| A2-assign | A | 2/2 -> 2/2 | 2/2 -> 2/2 |
| A3-assign-guarded | A | 2/2 -> 0/2  down | 2/2 -> 0/2  down |
| A4-impossible | A | 0/2 -> 0/2 | 0/2 -> 0/2 |
| B1-sequential | B | 0/2 -> 0/2 | 0/2 -> 0/2 |
| B2-max | B | 0/2 -> 0/2 | 0/2 -> 0/2 |
| B3-abs | B | 0/2 -> 0/2 | 0/2 -> 0/2 |
| C1-sqrt-loose | C | 1/2 -> 0/2  down | 0/2 -> 0/2 |
| C2-sqrt-tight | C | 0/2 -> 0/2 | 0/2 -> 0/2 |
| C3-loop-pinned | C | 2/2 -> 0/2  down | 0/2 -> 0/2 |
| C4-loop-invariant | C | 2/2 -> 0/2  down | 0/2 -> 0/2 |

## Aggregate

| Config | Law set | Solved | Calls/case | Wall s/case | Malformed | Budget aborts |
|---|---|---|---|---|---|---|
| llama3.1 | core (5 laws) | 9/22 (41%) | 15.9 | 42.4 | 12/350 (3%) | 10 |
| llama3.1 | extended (9 laws) | 2/22 (9%) | 18.0 | 48.6 | 44/396 (11%) | 8 |
| qwen3.5-nothink | core (5 laws) | 6/22 (27%) | 9.0 | 31.9 | 15/198 (8%) | 2 |
| qwen3.5-nothink | extended (9 laws) | 3/22 (14%) | 3.8 | 12.5 | 50/83 (60%) | 0 |

## Did the models actually reach for the new laws?

| Config | New law | Proposed | Accepted | Share of proposals |
|---|---|---|---|---|
| llama3.1 | flexible_sequential | 5 | 0 | 1.2% |
| llama3.1 | initialized_skip | 0 | 0 | 0.0% |
| llama3.1 | strengthen_post | 165 | 2 | 38.9% |
| llama3.1 | weaken_pre | 0 | 0 | 0.0% |
| qwen3.5-nothink | flexible_sequential | 0 | 0 | 0.0% |
| qwen3.5-nothink | initialized_skip | 0 | 0 | 0.0% |
| qwen3.5-nothink | strengthen_post | 1 | 0 | 1.2% |
| qwen3.5-nothink | weaken_pre | 12 | 0 | 14.5% |

## Full law histogram, extended arm (proposed -> accepted)

| Config | assignment | skip | sequential | alternation | iteration | strengthen_post | weaken_pre | initialized_skip | flexible_sequential | unknown |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.1 | 56->30 | 0->0 | 1->1 | 124->47 | 0->0 | 165->2 | 0->0 | 0->0 | 5->0 | 73->0 |
| qwen3.5-nothink | 2->2 | 18->1 | 0->0 | 0->0 | 0->0 | 1->0 | 12->0 | 0->0 | 0->0 | 50->0 |

## Errors in the extended arm


### llama3.1
- `Unexpected token Token('SLASH', '/') at line 1, column 27.` x14
- `Unexpected token Token('SLASH', '/') at line 1, column 34.` x10
- `Unexpected token Token('SLASH', '/') at line 1, column 28.` x6
- `Unexpected token Token('LPAR', '(') at line 2, column 4.` x2
- `Unexpected token Token('SLASH', '/') at line 1, column 43.` x2
- `No terminal matches '"' in the current parser context, at line 1 col 28` x2
- `Unexpected token Token('COLON', ':') at line 1, column 20.` x1
- `No terminal matches '"' in the current parser context, at line 1 col 27` x1

### qwen3.5-nothink
- `Unexpected token Token('COLON', ':') at line 1, column 20.` x35
- `Unexpected token Token('LPAR', '(') at line 1, column 22.` x7
- `No terminal matches '"' in the current parser context, at line 1 col 32` x2
- `Unexpected token Token('DOT', '.') at line 1, column 29.` x2
- `Expecting ',' delimiter: line 1 column 1781 (char 1780)` x1
- `Unexpected token Token('DOT', '.') at line 1, column 33.` x1
- `Unexpected token Token('LPAR', '(') at line 2, column 10.` x1
- `No terminal matches '"' in the current parser context, at line 1 col 35` x1

### 2.6 What this means

1. **The Study 1 hypothesis is refuted for these models.** Lemma 6.2 is not the
   blocker on Tier B. The blocker is that 8-9B models cannot reliably *choose*
   the right law from a nine-way menu, and adding options makes the choice worse,
   not better.

2. **This is consistent with the paper.** Refine4LLM's ablation shows extended
   laws changing pass rate not at all (87.8% -> 87.8%, Table 9); what moved the
   number was **instruction tuning** (87.8% -> 91.5%). The paper's own data says
   the laws buy refinement *time*, not correctness. Study 2 reproduces that,
   with the extra finding that for small models the wider law set actively hurts.

3. **The remaining levers are the interface, not the calculus:** fix the JSON
   escaping, give the model worked examples (few-shot), or narrow rather than
   widen the choice at each step. Study 1's baseline showed these models write
   correct code for all ten solvable cases in one shot; the difficulty is
   entirely in the refinement protocol.

### 2.7 Threats to validity

- Two repeats per cell. Within-cell variance is large: `C1-sqrt-loose` on
  llama3.1 gave SUCCESS in 1 call and a 30-call budget abort on consecutive
  repeats. Only the tier and aggregate rows above should be read; individual
  cells are noise.
- "More laws" is confounded with "longer prompt" (section 2.3).
- The progress guard and depth bound were introduced in this study. They are
  necessary for either arm to terminate, but they are new, and the core arm here
  is therefore not the core arm of Study 1.
- Only two models, one prompt, one temperature.

---

## 3. Reproducing

```bash
# both arms, one model resident at a time
bash benchmarks/run_lawcmp.sh

# or a single arm
python benchmarks/run_bench.py --configs llama3.1 --repeats 2 \
  --laws core --max-depth 6 --budget 30 \
  --out benchmarks/results/results_lawcmp.jsonl

python benchmarks/compare_laws.py
```

New files relative to Study 1:

- `benchmarks/run_lawcmp.sh` — memory-safe two-arm driver
- `benchmarks/compare_laws.py` — core-vs-extended aggregation
- `benchmarks/results/results_lawcmp.jsonl` — per-trial records, each tagged
  with `law_arm` and the exact `law_set` that was registered
- `FormalLLM/tests/test_progress_guard.py` — regression tests for the guard
