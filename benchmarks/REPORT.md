# Evaluating Local LLMs as Refinement Guides in FormalLLM

An empirical study of a personal implementation of **Refine4LLM**
(Cai, Hou, Sanan, Luan, Lin, Sun & Dong, *Automated Program Refinement: Guide and
Verify Code Large Language Model with Refinement Calculus*), run against local
models served by Ollama.

*187 trials across 7 configurations. All tables are generated from
`benchmarks/results/*.jsonl` by `benchmarks/analyse.py`; see "Reproducing".*

---

## 1. What this measures

Refine4LLM does not ask an LLM to write a program. It asks the LLM to pick the
**next refinement law** and supply its **parameters**, then discharges the
resulting proof obligation with an ATP (here, Z3). The LLM is a search heuristic
over a proof tree; correctness comes from the calculus, not the model.

So the question is not "can the model write code?" but three sharper ones:

1. **Law selection** — given a specification, does it pick a law that can work?
2. **Parameter synthesis** — can it produce the witness (the assignment
   expression, the guard, the intermediate assertion, the variant) that makes
   the proof obligation discharge?
3. **Feedback use** — when Z3 hands back a counterexample, does the next attempt
   get better, or does it repeat itself?

A model can be excellent at (1) and useless at (2), and the pass/fail number
alone will not tell you which. This benchmark separates them.

## 2. Setup

| | |
|---|---|
| Engine | this repo (`FormalLLM/`), with the fixes in §3 applied |
| Prover | Z3 via `z3-solver`, default tactics, no timeout set |
| Serving | Ollama, `/api/generate`, `format: json`, `temperature 0.2`, `num_predict 512` |
| Retries | `max_retries = 4` per node; a law is blacklisted at a node after it leads to a dead end |
| Budget | 30 LLM calls per trial (100 for the `llama3.1-wide` arm) |
| Repeats | 3 per (config, case); 2 for `llama3.1-wide` |

### Configurations

| Name | Model | Params | Notes |
|---|---|---|---|
| `oracle` | — | — | Replays hand-written perfect moves. A **lower bound** on what the engine can reach. |
| `llama3.1` | `llama3.1:latest` | 8.0B Q4_K_M | No reasoning mode. |
| `qwen3.5-nothink` | `qwen3.5:latest` | 9.7B Q4_K_M | `think: false`. |
| `qwen3.5-think` | `qwen3.5:latest` | 9.7B Q4_K_M | `think: true`. |
| `ornith` | `ornith:9b` | 9.0B Q4_K_M | qwen35 family; no reasoning mode. |
| `ornith-think` | `ornith:9b` | 9.0B Q4_K_M | `think: true`. |
| `llama3.1-wide` | `llama3.1:latest` | 8.0B Q4_K_M | Same model, 100-call budget. |

The `oracle` arm matters more than it looks. Without it, an engine bug and a
model failure are indistinguishable — both show up as "did not solve it".

It is a lower bound, not a ceiling: a model can find a refinement the playbook
never scripted, and llama3.1 did exactly that on `C3`. The "Solvable?" column in
§5 therefore marks a case solvable once *any* arm produced a verified program.

### Cases

Eleven specifications in three tiers (`benchmarks/cases.py`):

| Tier | Shape | Cases |
|---|---|---|
| A | One terminal law (`skip` / `assignment`) | `A1-skip`, `A2-assign`, `A3-assign-guarded`, `A4-impossible` |
| B | One structural decomposition, then terminals | `B1-sequential`, `B2-max`, `B3-abs` |
| C | The paper's hard cases | `C1-sqrt-loose`, `C2-sqrt-tight`, `C3-loop-pinned`, `C4-loop-invariant` |

Two are deliberate negative controls. `A4-impossible` has an unsatisfiable
postcondition — nothing refines it, and the metric of interest is how much
budget a model burns before giving up. `C3-loop-pinned` writes `i = 0` into the
precondition, which this engine reuses verbatim as the loop invariant, so no
body can preserve it; it probes that limitation rather than the model.

---

## 3. Engine defects found before any model could be measured

The oracle arm failed on cases that are provably refinable. Five defects had to
be fixed first. All of these are in my implementation, not in the paper.

### 3.1 The iteration law was unreachable

`agent/refiner.py` wired the iteration branch as:

```python
roles["init"] = graph.create_node(result.sub_specs[0])
roles["body"] = graph.create_node(result.sub_specs[1])
```

but `IterationLaw` emits the initialisation sub-spec only when the precondition
differs from the invariant:

```python
if spec.precondition.expr != invariant_expr:   # invariant_expr IS spec.precondition.expr
```

That comparison is an object against itself, so it is never true, so
`sub_specs` always has length 1, so the `[1]` always raised
`IndexError: list index out of range`. **Every `iteration` proposal by every
model died in the harness, not in the prover.** Fixed by branching on
`len(result.sub_specs)`, plus the matching case in `graph.reconstruct_program`.

### 3.2 The variant-decrease obligation degenerated to `false`

`to_previous_state` rewrote `V` into `V0` only for `Variable` nodes:

```python
if isinstance(node, Variable):
    return VariablePreviousState(node.name)
```

But `llm/parser.py` parses LLM-supplied expressions through a wrapper spec with
**no** `params`, and `resolve_names` reclassifies every unbound name as `Const`.
`Const` is not a subclass of `Variable`. So the guard and variant coming from
the model consisted entirely of `Const` nodes, none were rewritten, and the body
postcondition `I ∧ (V < V0)` came out as `I ∧ (V < V)` — unsatisfiable. Fixed by
matching `(Variable, Const)`.

### 3.3 `V0` was never tied to the pre-state

The body sub-spec was `[I ∧ G, I ∧ V < V0]`. `V0` appears only in the
postcondition, so it is a free logical constant and the obligation is
unprovable for any body. The standard formulation captures it in the
precondition; the body must be

```
[I ∧ G ∧ V = V0,  I ∧ V < V0]
```

Added the `V = V0` conjunct.

### 3.4 Declared types were dropped before the solver

Laws build obligations from `spec.precondition.expr` — the bare expression, not
the `Definition` that carries the `params`. `Z3Translator` then defaulted every
unseen name to `z3.Real`. So `(N:int)(i:int)` was solved over the **reals**,
where `i < N ⇒ i + 1 ≤ N` is false (`i = 0, N = 0.5`). Integer loop reasoning was
silently unsound-by-omission. Fixed by threading `params` onto `ProofObligation`
and seeding the translator's environment with declared sorts (and their `x0`
twins).

### 3.5 Reasoning models returned empty strings

`OllamaProvider` read only `result["response"]`. With `format: json`, a thinking
model (qwen3.5) puts its JSON in the separate `thinking` channel and leaves
`response` empty. Unpatched, **qwen3.5 would have scored 0% with a
"Expecting value" parse error on every single call** — a measurement artefact
that looks exactly like total model failure. The provider now falls back to the
thinking channel and records which channel was used.

After these fixes `pytest FormalLLM/tests/` still passes 18/18, and the oracle
solves 8 of 11 cases. A ninth (`C3`) was later shown solvable by llama3.1.

---

## 4. The transport layer corrupts L_spec

This is the largest single effect in the study, and it is not a property of any
model.

L_spec spells conjunction `/\` and disjunction `\/`. The provider requests
`format: json`. Inside a JSON string, `\` is an escape character, and
`llm/prompts.py` never tells the model to escape it. The results:

| Model emits | JSON decoder yields |
|---|---|
| `A \/ B` (disjunction) | `A / B` — **silently becomes division** |
| `A /\ B` (conjunction) | `JSONDecodeError: Invalid \escape` |
| `A /\geq B` | `JSONDecodeError: Invalid \escape` |
| `A /\reateroreq B` | `A /<CR>eateroreq B` — silently mangled to a control character |
| `A /\\ B` (escaped) | `A /\ B` ✓ |

The disjunction case is the dangerous one: it does not fail, it **changes the
meaning of the formula** and hands the altered formula to Z3.

Observed live in the run — llama3.1 on `B2-max` proposed
`{"variable": "m", "expr": "(A \/ B)"}`, which reached the parser as `A / B`.

Any case whose answer needs a logical connective — every alternation guard, every
non-trivial intermediate assertion — is fighting the encoding before the model's
reasoning is even relevant.

---

## 5. Results

187 trials. `llama3.1-wide` is llama3.1 re-run with the per-trial call budget
raised from 30 to 100 (2 repeats), to test whether its failures were budget-bound.

## Per-case outcomes (successes / attempts)

| Case | Tier | Solvable? | llama3.1 | llama3.1-wide | qwen3.5-nothink | qwen3.5-think | ornith | ornith-think |
|---|---|---|---|---|---|---|---|---|
| A1-skip | A | yes (first: oracle) | 3/3 | 2/2 | 3/3 | 0/3 exhaustedx3 | 3/3 | 3/3 |
| A2-assign | A | yes (first: oracle) | 3/3 | 2/2 | 3/3 | 2/3 exhaustedx1 | 3/3 | 3/3 |
| A3-assign-guarded | A | yes (first: oracle) | 3/3 | 1/2 exhaustedx1 | 3/3 | 1/3 exhaustedx2 | 2/3 budgetx1 | 2/3 budgetx1 |
| A4-impossible | A | none found | 0/3 exhaustedx3 | 0/2 exhaustedx2 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx2,budgetx1 | 0/3 exhaustedx3 |
| B1-sequential | B | yes (first: oracle) | 0/3 exhaustedx3 | 0/2 exhaustedx2 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 budgetx3 | 0/3 exhaustedx2,budgetx1 |
| B2-max | B | yes (first: oracle) | 0/3 exhaustedx3 | 0/2 exhaustedx2 | 0/3 budgetx3 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx2,budgetx1 |
| B3-abs | B | yes (first: oracle) | 0/3 exhaustedx3 | 0/2 exhaustedx2 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx2,budgetx1 | 0/3 budgetx2,exhaustedx1 |
| C1-sqrt-loose | C | yes (first: oracle) | 3/3 | 2/2 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx3 |
| C2-sqrt-tight | C | none found | 0/3 budgetx3 | 0/2 budgetx2 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx3 | 0/3 exhaustedx3 |
| C3-loop-pinned | C | yes (first: llama3.1) | 2/3 exhaustedx1 | 2/2 | 0/3 budgetx3 | 0/3 exhaustedx3 | 0/3 budgetx2,exhaustedx1 | 1/3 budgetx2 |
| C4-loop-invariant | C | yes (first: oracle) | 3/3 | 2/2 | 2/3 budgetx1 | 3/3 | 0/3 budgetx3 | 0/3 budgetx3 |

## Aggregate per configuration

| Config | Trials solved (solvable cases) | Trials solved (all cases) | LLM calls/case | Wall s/case | Mean latency s | Malformed output | Z3-rejected | Budget aborts |
|---|---|---|---|---|---|---|---|---|
| oracle | 8/9 (89%) | 8/11 (73%) | 2.8 | 0.0 | - | 0/31 (0%) | 12 | 0 |
| llama3.1 | 17/27 (63%) | 17/33 (52%) | 5.6 | 15.9 | 2.9 | 17/185 (9%) | 86 | 3 |
| llama3.1-wide | 11/18 (61%) | 11/22 (50%) | 11.5 | 31.9 | 3.0 | 21/253 (8%) | 86 | 2 |
| qwen3.5-nothink | 11/27 (41%) | 11/33 (33%) | 9.3 | 31.4 | 3.7 | 24/307 (8%) | 50 | 7 |
| qwen3.5-think | 6/27 (22%) | 6/33 (18%) | 3.7 | 35.6 | 9.5 | 99/122 (81%) | 16 | 0 |
| ornith | 8/27 (30%) | 8/33 (24%) | 15.9 | 59.4 | 3.7 | 65/526 (12%) | 193 | 11 |
| ornith-think | 9/27 (33%) | 9/33 (27%) | 14.1 | 52.9 | 3.5 | 59/464 (13%) | 136 | 10 |

## Law selection (proposed -> accepted by Z3)

| Config | assignment | skip | sequential | alternation | iteration | unknown |
|---|---|---|---|---|---|---|
| llama3.1 | 119 -> 30 | 0 -> 0 | 21 -> 15 | 25 -> 25 | 3 -> 0 | 57 -> 0 |
| llama3.1-wide | 162 -> 74 | 0 -> 0 | 65 -> 60 | 5 -> 5 | 0 -> 0 | 65 -> 0 |
| qwen3.5-nothink | 73 -> 12 | 59 -> 1 | 8 -> 3 | 27 -> 10 | 116 -> 115 | 152 -> 0 |
| qwen3.5-think | 19 -> 6 | 3 -> 0 | 0 -> 0 | 0 -> 0 | 1 -> 0 | 99 -> 0 |
| ornith | 34 -> 10 | 256 -> 34 | 73 -> 39 | 10 -> 5 | 88 -> 58 | 165 -> 0 |
| ornith-think | 54 -> 12 | 199 -> 36 | 62 -> 34 | 15 -> 9 | 74 -> 38 | 131 -> 0 |

## Failure taxonomy (error messages from malformed proposals)


### llama3.1
- `Unexpected token Token('LPAR', '(') at line 2, column 4.` x9
- `Unexpected token Token('NAME', 'A') at line 1, column 39.` x2
- `Unexpected token Token('SLASH', '/') at line 1, column 29.` x2
- `Unexpected token Token('LPAR', '(') at line 1, column 34.` x1
- `Unexpected token Token('NAME', 'A') at line 1, column 22.` x1
- `Unexpected token Token('MORETHAN', '>') at line 1, column 41.` x1
- `Unexpected token Token('NAME', 'and') at line 1, column 25.` x1

### llama3.1-wide
- `Unexpected token Token('LPAR', '(') at line 2, column 4.` x8
- `Unexpected token Token('SLASH', '/') at line 1, column 27.` x5
- `Unexpected token Token('SLASH', '/') at line 1, column 28.` x2
- `Unexpected token Token('NAME', 'A') at line 1, column 39.` x1
- `Unexpected token Token('LPAR', '(') at line 1, column 35.` x1
- `No terminal matches '?' in the current parser context, at line 1 col 26` x1
- `No terminal matches '?' in the current parser context, at line 1 col 25` x1
- `Unexpected token Token('MORETHAN', '>') at line 1, column 41.` x1

### qwen3.5-nothink
- `Unexpected token Token('LPAR', '(') at line 1, column 22.` x23
- `No terminal matches '|' in the current parser context, at line 1 col 27` x1

### qwen3.5-think
- `Unknown law generated by LLM: None` x69
- `Unterminated string starting at: line 2 column 15 (char 16)` x10
- `Invalid control character at: line 1 column 3 (char 2)` x2
- `Unexpected token Token('LPAR', '(') at line 1, column 22.` x2
- `Unterminated string starting at: line 14 column 3 (char 2012)` x1
- `Unterminated string starting at: line 1 column 2 (char 1)` x1
- `Expecting ',' delimiter: line 1 column 206 (char 205)` x1
- `Expecting ',' delimiter: line 2 column 1239 (char 1240)` x1

### ornith
- `Unknown law generated by LLM: None` x27
- `Unterminated string starting at: line 2 column 16 (char 17)` x16
- `Unexpected token Token('LPAR', '(') at line 1, column 22.` x16
- `No terminal matches '!' in the current parser context, at line 1 col 20` x2
- `No terminal matches '"' in the current parser context, at line 1 col 34` x1
- `No terminal matches '^' in the current parser context, at line 1 col 22` x1
- `Unterminated string starting at: line 3 column 3 (char 2241)` x1
- `Unterminated string starting at: line 2 column 15 (char 16)` x1

### ornith-think
- `Unknown law generated by LLM: None` x23
- `Unterminated string starting at: line 2 column 16 (char 17)` x14
- `Unexpected token Token('LPAR', '(') at line 1, column 22.` x14
- `Unexpected token Token('NAME', 'y') at line 1, column 21.` x3
- `Unterminated string starting at: line 2 column 15 (char 16)` x2
- `Unexpected token Token('NAME', 'if') at line 1, column 20.` x1
- `Expecting ',' delimiter: line 2 column 1856 (char 1857)` x1
- `No terminal matches '"' in the current parser context, at line 1 col 34` x1

### 5.5 Reading the numbers

**llama3.1 (8B) beats both 9B models.** Parameter count does not predict
refinement-guidance ability here.

**Tier B is a total wipeout: 0/57 across every configuration**, while the oracle
solves all three cases in 3 calls each. One structural decomposition followed by
two terminal steps is beyond every local model tested, in two model families.
This is the most robust result in the study.

**More budget does not help.** `llama3.1-wide` got 3.3x the call budget and
solved slightly *fewer* trials proportionally (61% vs 63%). It spent the extra
calls descending deeper, not recovering: `sequential` proposals rose 21 -> 65
and `B1`/`B2`/`B3` still went 0/6. The models are not budget-limited; they are
strategy-limited.

**Counterexample feedback changes parameters, not strategy.** The law histograms
show each model locking onto one law and retrying it:

- llama3.1 proposed `skip` **0 times in 185 calls** -- even on `A1-skip`, where
  it is the answer. It "solved" A1 with the ill-typed `x = (x > 0)` instead.
- ornith proposed `skip` **256 times**, accepted 34, hammering it against Z3
  rejections rather than switching law.

Neither reads a counterexample and concludes "wrong law". They conclude "wrong
expression for this law".

**`alternation` is accepted 25/25 for llama3.1** because `AlternationLaw` and
`SequentialCompositionLaw` emit *no proof obligations*. Nothing can reject them,
so the refiner descends unboundedly -- on `C2`, llama3.1 built a 49-node tree
from a 23-deep chain of accepted alternations. That is what the budget aborts
are. `AutomatedRefiner` has no depth bound and no cycle detection.

**Cost.** ornith is the most expensive arm by a wide margin -- 15.9 calls and
59s per case, roughly 3x llama3.1's cost for half the success rate.

**The negative control worked.** `A4-impossible` was correctly abandoned by all
six configurations; no model fabricated a proof of an unsatisfiable spec.

### 5.6 Degenerate successes

Some passes are not real programs, and the engine cannot tell:

| Arm / case | "Verified" program | Why it is wrong |
|---|---|---|
| llama3.1 / `A1-skip` | `x = (x > 0)` | assigns a Bool to an int; z3py coerces to `If(0<x,1,0)` and proves it |
| llama3.1 / `C3-loop-pinned` | `N = 0` | overwrites its own input constant |
| several / `C4-loop-invariant` | `i = N` | valid, but needs no loop -- the case under-tests iteration |

Two engine gaps behind this: **no type checking** between L_spec expressions and
the program language, and **no frame condition** -- the calculus writes
`x:[P,Q]` with an explicit assignable-variable list, which this implementation
drops, so any name may be assigned. Reported pass rates are therefore *upper*
bounds.

### 5.7 Threats to validity

- Only two genuine model families (llama3.1; qwen3.5 and ornith are both qwen35).
- 11 cases, 2-3 repeats: wide confidence intervals on any single cell.
- The oracle is a *lower* bound on solvability, not a ceiling -- llama3.1 solved
  `C3` via a move the playbook never scripted.
- `C4` admits a trivial non-loop solution.
- One prompt, one temperature (0.2). No prompt engineering was attempted; the
  JSON-escaping defect in section 4 alone would confound such a comparison.

---
---

## 6. Baseline: the same specs, asked for code directly

The refinement numbers above only mean something against a control. So each model
was given the *same* eleven specifications plus a one-line English intent, and
asked for a Python function -- no refinement calculus, no prover, one call. This
mirrors the paper's `NL`/`FS` baseline columns (their Table 6). Correctness is
decided by executing the generated function on 12 generated inputs per case and
checking the postcondition, in a subprocess with a 10 s timeout.

| Case | llama3.1 | qwen3.5-nothink | qwen3.5-think | ornith | ornith-think |
|---|---|---|---|---|---|
| `A1-skip` | PASS | PASS | PASS | PASS | PASS |
| `A2-assign` | PASS | PASS | PASS | PASS | PASS |
| `A3-assign-guarded` | PASS | PASS | PASS | PASS | PASS |
| `A4-impossible` | fail | fail | fail | fail | fail |
| `B1-sequential` | PASS | PASS | PASS | PASS | PASS |
| `B2-max` | PASS | PASS | PASS | PASS | PASS |
| `B3-abs` | PASS | PASS | PASS | PASS | PASS |
| `C1-sqrt-loose` | PASS | PASS | fail (exec_error) | PASS | PASS |
| `C2-sqrt-tight` | PASS | PASS | fail (exec_error) | PASS | PASS |
| `C3-loop-pinned` | PASS | PASS | PASS | PASS | PASS |
| `C4-loop-invariant` | PASS | PASS | PASS | PASS | PASS |

| Config | Baseline solved (of 10) | Refinement pipeline | Baseline time |
|---|---|---|---|
| `llama3.1` | **10/10** | 63% (17/27) | 33s |
| `qwen3.5-nothink` | **10/10** | 41% (11/27) | 46s |
| `qwen3.5-think` | **8/10** | 22% (6/27) | 997s |
| `ornith` | **10/10** | 30% (8/27) | 80s |
| `ornith-think` | **10/10** | 33% (9/27) | 84s |

`A4-impossible` fails for every model, as it must -- the postcondition is
unsatisfiable. It is the control showing the harness is not rubber-stamping.

### What this tells us

**Four of five models solve every solvable case in one shot**, in well under two
minutes of wall time, including the three Tier-B cases and `C2-sqrt-tight` that
the refinement pipeline never solved for *any* model at *any* budget.

Side by side on the cases the pipeline could not do:

| Case | Refinement, best of any model | Baseline |
|---|---|---|
| `B1-sequential` | 0/15 | 4 of 5 models pass |
| `B2-max` | 0/15 | 5 of 5 pass |
| `B3-abs` | 0/15 | 5 of 5 pass |
| `C2-sqrt-tight` | 0/15 | 4 of 5 pass |

llama3.1 on `B2-max`, which it failed 0/3 through the refinement interface:

```python
def f(A: int, B: int) -> int:
    if A >= B:
        return A
    else:
        return B
```

That is exactly the alternation refinement with guard `A >= B`. Through the
refinement interface the same model proposed `m := (A \/ B)`, which the JSON
decoder silently turned into `A / B`.

qwen3.5-nothink on `C4-loop-invariant` -- the loop the engine never synthesised:

```python
def f(i: int, N: int) -> int:
    while i < N:
        i += 1
    return i
```

**Conclusion: the models are not too weak to solve these problems.** They are
too weak to solve them through a zero-shot, example-free, JSON-encoded, five-law
refinement interface. The bottleneck measured in section 5 is mostly the
interface, not model capability.

### The one genuine model failure

`qwen3.5-think` scores 8/10, and the two misses are real over-thinking, not a
harness artifact. On `C1-sqrt-loose` ("return a number whose square is at most
N") it emitted 16,010 characters of reasoning and hit the 4096-token cap exactly
(`eval_count 4096`) without ever producing a function; the tail of the trace is
the model debating whether importing `math` counts as "self-contained". Its
baseline run took 997 s against llama3.1's 33 s for a better result. A larger cap
than 4096 was not tested, so it may finish eventually -- but spending 4096 tokens
on this problem is itself the finding.

This matches its behaviour in section 5, where the same rumination showed up as
an 81% malformed-output rate.

### Why this study's numbers differ from the paper's

With the baseline as a control, the gap decomposes into two causes:

1. **Model class.** The paper's *weakest* ablation -- core laws only, no extended
   laws, no instruction tuning, i.e. exactly this implementation's feature set --
   still scores 87.8%, because it runs on **GPT-4 instruction-tuned on classic
   refinement examples**. This study runs 8-9B models at 4-bit quantisation,
   zero-shot, with no worked examples in the prompt.

2. **Missing machinery.** No refinement library (their Table 8: fall-back rate
   9.45% with it, 26.87% without; 5.6 steps versus 21.4). Only the five core
   laws -- no Strengthen-Postcondition (Lemma 2.1), Weaken-Precondition (2.2),
   Flexible Sequential Composition (6.2), or Initialised Skip (6.1). That last
   gap is the likeliest single explanation for the Tier-B wipeout: this
   implementation's `sequential` law needs an intermediate `R` that works
   verbatim on both halves, whereas Lemma 6.2 only needs `P => A`, `B => C`,
   `D => Q` -- a far larger target to hit.

Neither cause is a defect in the paper. This study is closer to a measurement of
what Refine4LLM's scaffolding is worth: remove the library, the extended laws,
the tuning and the frontier model, and guidance quality collapses even though the
underlying models can write the programs directly.

---

## 7. Reproducing

```bash
pip install -r requirements.txt
ollama pull llama3.1 && ollama pull qwen3.5

# engine ceiling (instant, no LLM)
python benchmarks/run_bench.py --configs oracle --out benchmarks/results/oracle.jsonl

# the models
python benchmarks/run_bench.py \
  --configs llama3.1 qwen3.5-nothink qwen3.5-think \
  --repeats 3 --max-retries 4 --budget 30 --temperature 0.2 \
  --out benchmarks/results/results.jsonl

python benchmarks/analyse.py

# baseline: same specs, ask each model for code directly
python benchmarks/baseline.py   --configs llama3.1 qwen3.5-nothink qwen3.5-think ornith ornith-think
```

Layout:

- `benchmarks/cases.py` — the eleven specifications
- `benchmarks/oracle.py` — hand-written perfect moves (the ceiling)
- `benchmarks/harness.py` — instrumented single-trial runner
- `benchmarks/run_bench.py` — sweep driver
- `benchmarks/analyse.py` — aggregation into the tables above
- `benchmarks/baseline_cases.py` — NL intent, signature, inputs and postcondition
  checker for the direct-code-generation control
- `benchmarks/baseline.py` — baseline runner (subprocess-isolated, 10 s timeout)
- `benchmarks/baseline_code/<config>/<case>.py` — every program each model wrote,
  with model, spec and intent in a header comment
- `benchmarks/results/*.jsonl` — one JSON record per trial, including every raw
  model response, so any claim here can be re-derived
