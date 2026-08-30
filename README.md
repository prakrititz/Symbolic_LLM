# Proposal Prep — LLM + Formal Methods for Trustworthy Agents

> Reading notes on your supervisor's own work, plus the surrounding literature in code / law / medicine,
> oriented toward picking a proposal topic that **extends their program** rather than sitting beside it.
>
> Compiled 28 Aug 2026. Every claim carries an arXiv ID or venue.
> **Benchmark figures are as reported by their authors and are not independently reproduced** —
> re-check before putting any number in a written proposal.

---

## Table of contents

1. [First: the files in this folder](#1-first-the-files-in-this-folder)
2. [What the paper actually says](#2-what-the-paper-actually-says)
3. [The gaps *they* declare open](#3-the-gaps-they-declare-open)
4. [What's already been done on those gaps](#4-whats-already-been-done-on-those-gaps)
5. [Eight topics, ranked for this lab](#5-eight-topics-ranked-for-this-lab)
6. [Background: the three domains](#6-background-the-three-domains)
7. [How to run the meeting](#7-how-to-run-the-meeting)
8. [Bibliography](#8-bibliography)

---

## 1. First: the files in this folder

All three PDFs are **byte-identical** (197,121 bytes each) — one paper, saved three times:

```
CACM_LLM_FM.pdf
Position-Trustworthy-AI-Agents-Require-...-Formal-Methods.pdf
Position-Trustworthy-AI-Agents-Require-...-Formal-Methods (1).pdf
```

**The paper:** *Synergizing LLMs and Formal Methods for Neural-Symbolic Reasoning*
Jin Song Dong, Yufan Cai, Zhe Hou, Jing Sun, Hongshu Wang, Yedi Zhang, Xinyue Zuo
*Journal of the ACM*, 2025. (Also circulating as a Position paper — [OpenReview](https://openreview.net/forum?id=wkisIZbntD).)

**The group:** NUS (Dong, Cai, Wang, Zhang, Zuo) + Griffith (Zhe Hou) + Auckland (Jing Sun).
This is the PAT / model-checking lineage — Dong is a co-author of the original PAT toolkit (CAV 2009).

> ⚠️ Note the file naming: you may be missing the actual *Position* paper, if it's a separate
> document from the JACM article. Worth checking with your prof that you have both.

---

## 2. What the paper actually says

Read this section before the meeting. Being able to restate their paradigm in your own words is
worth more than any topic idea.

### 2.1 The core argument

- LLM hallucination is **not a bug to be trained away** — it is mathematically inherent to the
  probabilistic objective (they cite Xu et al., *Hallucination is Inevitable*, `arXiv:2401.11817`).
- Formal methods give rigorous guarantees but have a steep learning curve and poor accessibility.
- Therefore: **LLMs propose, formal methods dispose.**

Their motivating example is deliberately humble: a 3-digit combination puzzle that older LLMs get
wrong with fluent-but-invalid reasoning. Claude 4 translated it into SMT-LIB and **Z3 solved it in
0.01 seconds on a laptop**. The point is not that the puzzle is hard; it's that the *right division of
labour* makes it trivial.

### 2.2 The paradigm

> **LLMs explore the design space by proposing candidate artifacts; FM backends enforce a
> certificate-based acceptance boundary grounded in explicit assurance targets.**

The key concept is the **certificate** — machine-checkable evidence produced by the FM backend:
a localized conflict explanation (unsat core), a violating execution trace (counterexample), or an
undischarged proof obligation.

They deliberately choose **external** FM (constrain / check / guide LLM outputs without touching
model internals) over tightly-integrated approaches like Logical Neural Networks or Scallop —
arguing internal integration is "possible but prohibitively resource-intensive."

Architecture components: a Task Automation LLM (orchestrator), an **Auto-formalization LLM**,
a Designing LLM, a Coding LLM, RAG for domain knowledge, and FM engines (SMT solvers, theorem
provers, model checkers) whose outputs feed a repair loop.

### 2.3 The five design rules — memorise these

| Rule | Content |
|---|---|
| **1. Assurance target** | State the artifact that must be correct and the properties defining correctness. Write the acceptance claim as *"this output is acceptable because ⟨property⟩ holds for ⟨artifact⟩."* If you can't state it precisely, design drifts toward optimising fluency instead of correctness |
| **2. Backend FM choice** | Match backend to **property class** and domain of quantification. SMT → constraint satisfiability/consistency, returns **unsat cores**. Model checking → behavioral/temporal properties, returns **counterexample traces**, first-class safety/liveness/fairness. Theorem proving / refinement → semantic, unbounded correctness via **proof obligations**. Lighter-weight fallbacks: type systems, abstract interpretation, contract checking |
| **3. LLM–FM interface** | Define the contract: what the LLM may propose (candidates, decompositions, repairs) and what FM must return on failure. **Treat formal failures as *typed signals*, not generic "try again"** — organize repair around channels: inconsistency / counterexample / unsatisfied obligation |
| **4. Integration pattern** | Match coupling to dominant failure mode. Decision/compliance → **consistency-guarded deliberation**. System behaviors → **counterexample-guided refinement**. Component synthesis → **proof-obligation-guided synthesis**. Combine across layers: certify high-level model first, then constrain lower-level synthesis |
| **5. Acceptance guard** | State explicitly what certificate gates acceptance and what it certifies. Stronger certificates → higher iteration cost, narrower applicability. **FM is the correctness filter, not an optional add-on**; keep clean separation between candidate generation and certificate-based validation |

### 2.4 The three case studies

| # | Name | Direction | FM backend | Certificate | Reference |
|---|---|---|---|---|---|
| 1 | **Legal AI (L4L)** | FM4LLM | SMT (Z3) | Unsat core | Chen, Cai, Hou, Dong — `arXiv:2511.21033` |
| 2 | **PAT-Agent** | LLM4FM | Model checking (PAT/CSP#) | Counterexample trace | Zuo et al., **ASE 2025** |
| 3 | **Trustworthy AI Coder** | "They are one" | Refinement calculus + ATP | Discharged proof obligations | Cai et al., **POPL 2025** |

**Case study 1 — Legal (FM4LLM: formal methods improving the LLM).**
Each statutory clause is parsed into a typed rule `Rule(c) := ⟨Actor, Action, Cond, Penalty⟩` and
compiled into a first-order implication. A **Prosecutor LLM** (accusatory stance) and an
**Attorney LLM** (exculpatory stance) independently extract fact predicates and cited clauses.
A neutral **Auto-formalizer LLM** turns their evidence into SMT-LIB; Z3 checks it. On UNSAT, the
**minimal unsatisfiable core** is extracted, mapped back to the original text, and used to instruct
the offending agent to drop contradictory clauses. A Judge LLM renders the verdict.
Their worked example (a Chinese narcotics case) yields 2 years + ¥10,000 against a ground truth of
1 year 2 months + ¥11,000. Reported as highest accuracy among SOTA methods.

**Case study 2 — PAT-Agent (LLM4FM: LLMs lowering the FM entry barrier).**
Four transformations: `T_plan: L_NL → Π → P`, `T_gen: P → M`, `V: M × Q → {MATCH, MISMATCH} × C`,
`T_repair: M × C × R → M`. A Planning LLM extracts constants/variables/actions/guards and produces a
generation plan; a Coding LLM emits CSP#; PAT verifies; counterexamples drive a Repair Agent that
fixes **only the faulty region** rather than regenerating.
Reported: **99.6% requirement-translation accuracy**; Claude 3.7 Sonnet produces near-perfect CSP#
syntax first try; **3–4 repair iterations typically suffice**.
Their closing line is the pitch: *"automakers can now verify their designs without the excuse of
'But we do not have formal methods engineers.'"*

**Case study 3 — Trustworthy AI Coder.**
GPT-5 writes a plausible `sqrt` function that is **wrong** — `abs(x_next - x) <= e` does not imply
`abs(x_next² - N) <= e`. Their fix uses Morgan's **refinement calculus**: start from a first-order
logic spec, apply correctness-preserving transformations (assignment introduction, guard
strengthening, loop introduction), with the LLM predicting which refinement law to apply,
instantiating it, and emitting the induced proof obligation; an ATP discharges the POs. Failures
return the failing proof state, and the LLM revises, switches rule, or backtracks.

> **The killer result to quote:** LLM pass rates *decrease* as you add test cases (bugs remain).
> Their method's pass rate is **constant regardless of test count, because the programs are proven
> correct.** Remaining failures are mostly *theorem-prover timeouts*, not incorrect code.

---

## 3. The gaps *they* declare open

This is where your proposal should live. Section 6 of the paper — "Mitigating Auto-formalization
Risk" — is effectively a research agenda handed to you.

### 3.1 The stated central problem

> **Semantic under-specification.** "Natural language omits assumptions, scopes, and constraints, so
> an auto-formalizer can produce a logically consistent but **intent-misaligned** specification that
> still passes solver checks and yields **certificates for the wrong target**."

And, crucially:

> "Formal methods act as **verifiers of consistency, not arbiters of semantic truth**. Bridging the
> informal–formal gap therefore remains an open research challenge."

**Restated as the hole in their own architecture:** Design Rule 5 puts an acceptance guard on the
*output artifact*. **There is no acceptance guard on the specification itself.** The autoformalizer
is the one unverified component in a system whose entire selling point is verification.

### 3.2 Their explicit future-work list

From §6 and §7, they name these as the way to close the gap:

1. **N-version auto-formalization** — generate multiple independent formalizations (different LLMs
   or prompt/decoding variants), filter with lightweight formal checks (well-formedness/type
   constraints, satisfiability, non-triviality, consistency against fixed background constraints).
   **Material disagreement is treated as a high-risk signal and surfaced explicitly rather than
   silently resolved.**
2. **Router + specialists** — a system-level mixture-of-experts dispatching to domain- and
   logic-specific formalizers, keeping the same certificate-producing backend as the gate.
3. **Typed intermediate representations + constrained decoding** — LLM emits a type-checked schema
   compiled *deterministically* into the target formalism.
4. **Scenario-based semantic validation** — round-trip paraphrases and auto-generated
   **"should / should-not" scenarios** checked against both original intent and the formal solver.

### 3.3 Their named application frontiers

> "compliance analysis, protocol verification, cyber-physical safety, and synthesis of critical components"

Plus the Lean ecosystem: Mathlib, and **CSLib — The Lean Computer Science Library**
(Barrett et al., `arXiv:2602.04846`), which they flag as enabling "results beyond what either could
readily do alone."

### 3.4 The gap they *don't* name — and you should

**Medicine is missing.** Their case studies cover law (SMT), systems (model checking), and code
(theorem proving). Healthcare appears once, in the introduction's list of LLM application areas,
and never again. Given that clinical guidelines are *already* a classical formal-methods target
(see §4.3), this is the most natural fourth case study in the paper — and it is unclaimed.

---

## 4. What's already been done on those gaps

I checked the literature against each of their future-work items so you don't propose something
already published. **This section is your novelty defence.**

### 4.1 N-version autoformalization — ⚠️ partially scooped

**"Neurosymbolic Auditing of Natural-Language Software Requirements"** (`arXiv:2605.13817`) does
almost exactly the N-version idea: it samples multiple independent SMT formalizations of the same
requirement and compares them with **bidirectional SMT equivalence checking**, treating persistent
disagreement as evidence that the requirement admits more than one plausible reading.

**What this means for you:** the mechanism is published, in the *software-requirements* domain.
Still open: (a) doing it where formalization targets are **statutes or clinical guidelines**, not
requirements; (b) turning disagreement into a **quantitative risk certificate** rather than a binary
flag; (c) the router+specialists half, which nobody has built.
**Do not propose plain N-version-for-requirements.** Cite this paper and differentiate explicitly.

### 4.2 Autoformalization fidelity — an active, adjacent field

| Work | ID | Relevance |
|---|---|---|
| **ConsistencyCheck** | — | 859 expert-annotated items; binary "does this formal statement preserve the semantics?" **Even human experts make semantic errors in up to 38.5% of cases.** Devastating number for any human-confirmation-based mitigation — and their §6 assumes exactly that |
| **Verus-SpecGym** | `2605.26457` | Agentic environment for spec autoformalization. Finding: **specification autoformalization is a distinct bottleneck** — models that write correct code for a problem often fail to write a faithful spec for the same problem |
| Faithful Autoformalization via Roundtrip Verification and Repair | `2604.25031` | Their round-trip-paraphrase idea, already implemented |
| Evaluating Autoformalization Robustness via Semantically Similar Paraphrasing | `2511.12784` | Paraphrase-invariance as a fidelity test |
| ReForm: Reflective Autoformalization | `2510.24592` | Prospective bounded sequence optimization |
| Faults in Our Formal Benchmarking | `2606.29493` | Dataset defects in Lean theorem-proving benchmarks |
| Towards Autoformalization of LLM-generated Outputs for Requirement Verification | `2511.11829` | Closest to the SE-requirements framing |

> **Takeaway:** round-trip verification and paraphrase robustness are *taken*. The **certificate**
> framing — producing a machine-checkable artifact that bounds formalization risk, and gating
> acceptance on it — is **not**, and it is the natural extension of their own Design Rule 5.

### 4.3 Clinical guidelines + model checking — a 15-year-old literature with a stalled bottleneck

This is the important discovery. There is a substantial pre-LLM body of work:

- *Adopting model checking techniques for clinical guidelines verification* — **Artificial
  Intelligence in Medicine** (Elsevier)
- *Using model checking for critiquing based on clinical guidelines* — **Artificial Intelligence in
  Medicine**, 2008 — casts guideline *critiquing* in temporal logic; compares actual treatment
  derived from real patient data against the guideline as "ideal actions"
- *Analyzing Clinical Practice Guidelines Using a Decidable Metric Interval-Based Temporal Logic*
  (Springer)
- Reviews of care-pathway computerization document that **manual formalization is the adoption
  blocker** for process-oriented health information systems

**Read that against PAT-Agent.** The classical literature says: *model checking clinical guidelines
works, but nobody can afford to write the models.* PAT-Agent says: *we automated writing the models,
at 99.6% requirement-translation accuracy.* **These two literatures have not been joined.**
That is Topic 01.

### 4.4 Their own follow-on work — already in flight

- **Event-B Agent: Towards LLM Agent for Formal Model Synthesis and Repair** — Wang, Zuo, Sun, Li,
  Ait Ameur, Dong. **FSE 2026**, `arXiv:2605.17475`. Same group, extending the LLM4FM line to Event-B.
- **On Verifiable Legal Reasoning: A Multi-Agent Framework with Formalized Knowledge
  Representations** (`arXiv:2509.00710`) — an independent group, same idea as L4L. Check overlap.
- **ATA: A Neuro-Symbolic Approach to Autonomous and Trustworthy Agents** (`arXiv:2510.16381`).

> ⚠️ Ask whether an Event-B / Lean / CSLib direction is already assigned to another student before
> you commit to anything in that lane.

---

## 5. Eight topics, ranked for this lab

Ranked by **fit to their program × novelty × feasibility**. Every one is framed as
*LLM proposes → FM certifies*, because that is the lab's thesis.

---

### 🥇 Rank 01 — The missing fourth case study: FM4Medicine
**Auto-formalized clinical guidelines with counterexample-guided care-plan checking**

Their paper has case studies in law, systems, and code. **Medicine is absent.** Meanwhile a 15-year
AI-in-Medicine literature established that clinical practice guidelines can be model-checked in
temporal logic — and stalled because **manual formalization was unaffordable**. PAT-Agent solved
exactly that bottleneck for CSP#. Join them.

| | |
|---|---|
| **Assurance target** (DR1) | *"This care plan is acceptable because it satisfies the temporal properties derived from guideline G."* |
| **Backend** (DR2) | Model checking — the properties are inherently temporal/behavioral (sequencing, contraindication windows, escalation ordering, monitoring intervals). Their own Rule 2 selects it |
| **Certificate** (DR5) | A counterexample trace showing the concrete sequence of clinical actions that violates the guideline |
| **Pattern** (DR4) | Counterexample-guided refinement — same as PAT-Agent |
| **Build** | Planning LLM + Coding LLM pipeline from guideline prose → CSP# (or Event-B, reusing the group's newest work). Check retrospective care plans, or plans produced by a medical agent on MedAgentBench / AgentClinic, against the formalized guideline |
| **Measure** | Formalization accuracy vs. clinician annotation; violation detection rate; **how many guideline violations by an LLM medical agent are caught that no benchmark metric catches** |
| **Why it lands** | Reuses their tool, their paradigm, and their design rules; opens a new domain; the "excuse of no formal methods engineers" line applies *verbatim* to hospitals. And it converts medical agent evaluation from accuracy-scoring to **compliance-certification**, which is what regulators will actually demand |
| **Risk** | Guideline prose is more ambiguous than statutes — which is itself the §6 auto-formalization problem, so it feeds Topic 02. Mitigate by starting with a narrow, well-structured guideline (sepsis bundles, anticoagulation dosing, antibiotic stewardship) |

**Prior art to cite and differentiate from:** the AI-in-Medicine model-checking papers (pre-LLM,
manual formalization) and PAT-Agent (LLM formalization, non-medical domain). Nobody has bridged them.

---

### 🥈 Rank 02 — An acceptance guard for the auto-formalizer
**Turning formalization risk into a machine-checkable certificate**

Their Design Rule 5 gates the *output artifact* with a certificate. **The specification itself is
ungated** — the one unverified component in a verification-first architecture. §6 names this
precisely: a formalizer can yield "certificates for the wrong target."

| | |
|---|---|
| **Build** | A layered fidelity guard: (i) N-version formalization with bidirectional equivalence checking; (ii) auto-generated **should / should-not scenarios** discriminating candidate formalizations; (iii) a **quantitative risk score** compiled into a certificate that gates acceptance alongside the solver's |
| **Measure** | Detection of intent-misaligned-but-satisfiable specs. Build the eval set by **deliberately injecting semantic under-specification** (dropped scope, missing precondition, wrong quantifier) and measuring catch rate vs. round-trip and paraphrase baselines |
| **Why it lands** | It is the group's own §7 future work, and it makes their whole paradigm *sound* rather than merely useful. Publishable as infrastructure regardless of outcome |
| **Risk** | ⚠️ **Novelty pressure.** N-version SMT-equivalence is done for SE requirements (`2605.13817`); round-trip is done (`2604.25031`); paraphrase robustness is done (`2511.12784`). **Differentiate on three axes:** the certificate/risk-quantification framing, the domain (statutes and guidelines, not code requirements), and integration into an end-to-end acceptance guard rather than a standalone metric. Say this explicitly in the meeting — showing you know what's taken is worth more than the idea itself |

**Sharpest supporting fact:** ConsistencyCheck reports **human experts miss semantic errors in up to
38.5% of cases.** Their §6 mitigation is "the user manually confirms the formal specification."
That mitigation is empirically unreliable. Lead with this.

---

### 🥉 Rank 03 — Do certificates actually help the human?
**An empirical study of unsat cores and counterexample traces as expert-facing explanations**

The entire paradigm assumes a human validates the spec and consumes the certificate. **Nobody has
tested whether certificates improve expert decisions.** The reliance-calibration literature is
actively discouraging: standard interventions (numeric confidence, feature-based explanations)
**do not robustly improve calibration and can worsen over-reliance** (`arXiv:2502.13321`), and in one
clinical study physicians overestimated an AI's accuracy by ~30 percentage points.

| | |
|---|---|
| **Build** | A controlled study. Same underlying task (legal consistency check or care-plan check), three conditions: no explanation / natural-language LLM explanation / **formal certificate** (unsat core, counterexample trace). Measure whether experts correctly accept correct outputs and reject incorrect ones |
| **Measure** | Appropriate reliance — sensitivity *and* specificity, not raw accuracy. Whether certificates cause **over-**trust ("it's formally verified, so it's right") even when the spec is wrong |
| **Why it lands** | Cheap, fast, no GPUs. It **de-risks the group's entire program** by testing its human-facing assumption, and it's the kind of result that gets cited by everyone in LLM+FM. A negative result is *more* interesting than a positive one |
| **Risk** | Needs human subjects (ethics approval, participant recruitment). Start small — even 15–20 domain-trained participants gives a publishable pilot. Law students are more accessible than clinicians |

---

### Rank 04 — Certifying the *process*, not just the artifact
**Temporal-logic acceptance guards over agent tool-call traces**

Their certificates gate an output: a verdict, a model, a program. But an agent is a *trace of
actions*, and in law and medicine the **procedure is itself legally mandated** — conflict checks
before advice, contraindication checks before prescribing, consent before disclosure. Lift the
acceptance guard from the artifact to the run.

| | |
|---|---|
| **Build** | A specification language for professional-procedure constraints + a runtime monitor over the agent's tool-call trace that can block or roll back a violating action. Extends AgentLTL (`2607.02599`); the specification/verification/enforcement survey (`2608.14590`, 38 studies 2022–2026) is your related-work map |
| **Measure** | Violation rate with/without enforcement; the **utility cost** of enforcement (over-blocking) — this trade-off is exactly their DR5 "stronger certificates raise iteration cost" |
| **Why it lands** | A clean, principled extension of their Design Rule 4/5 into agentic settings, in the domains where "usually correct" is not an acceptable standard |
| **Risk** | Formalising real professional obligations needs domain experts. Overlaps Rank 01 — could be the second half of the same thesis |

---

### Rank 05 — Proof obligations as free process-reward signal
**Bridging their POPL work to the agentic-RL literature**

The SWE-agent field is spending enormous effort *learning* step-level reward models
(SWE-RM, `2512.21919`, 30B MoE; SWE-TRACE, `2604.14820`) because outcome-only reward is too sparse
for long trajectories. **The refinement calculus already emits a dense, objective, per-step
correctness signal for free: the discharged proof obligation.**

| | |
|---|---|
| **Build** | Use PO discharge/failure as ground-truth process supervision to train or evaluate a process reward model. Then test the interesting direction: does a PRM trained on formally-verified traces transfer to domains with *no* verifier? |
| **Measure** | PRM accuracy against PO ground truth vs. LLM-as-judge baselines; downstream test-time-scaling gains |
| **Why it lands** | Connects the lab's formal work to the hottest thread in agent training, and gives the SWE-RL community something it can't generate itself — **certified** process labels. Good joint-venue potential (PLDI/POPL ↔ ICLR/NeurIPS) |
| **Risk** | Refinement-calculus traces are a narrow distribution; transfer may simply fail. Frame transfer as the research question so a negative result still publishes |

---

### Rank 06 — Is Design Rule 2 actually right?
**Empirically validating property-class → FM-backend selection**

Design Rule 2 asserts that SMT suits satisfiability/consistency, model checking suits
behavioral/temporal, theorem proving suits unbounded semantic correctness. It is stated as expert
guidance and **never measured**. Test it.

| | |
|---|---|
| **Build** | A benchmark of tasks spanning property classes, run through all three backends, holding the LLM and prompt fixed. Report where the rule holds, where it breaks, and what the crossover costs are |
| **Measure** | Success rate, iteration count, wall-clock, and **failure mode by backend** (timeout vs. wrong answer vs. spec mismatch) |
| **Why it lands** | Converts your supervisor's design heuristic into a measured result — flattering, useful, and squarely within their frame. It is also the LLM+FM analogue of the coding-benchmark critique (`2606.17799`) about confounded components |
| **Risk** | Engineering-heavy (three toolchains). Low intellectual risk, moderate labour. A good *first* paper before a bigger thesis |

---

### Rank 07 — L4L beyond statute: what happens when law isn't a rule?
**Testing the limits of the compile-a-clause-to-a-typed-rule assumption**

L4L works because Chinese statutory law compiles cleanly into
`⟨Actor, Action, Cond, Penalty⟩`. Common-law reasoning — precedent, analogy, balancing tests,
open-textured standards like "reasonable" — does not.

| | |
|---|---|
| **Build** | Apply the L4L architecture to a common-law or Indian-law corpus. Characterise where the typed-rule abstraction holds, degrades, and fails. Where it fails, what is the right weaker certificate — a *partial* consistency check over the formalisable fragment? |
| **Measure** | Coverage (fraction of provisions formalisable), accuracy on the formalisable fragment, and honest failure analysis of the rest |
| **Why it lands** | Directly extends the group's own case study, and the legal-agent surveys explicitly flag **jurisdictional skew — datasets are heavily Chinese, common-law coverage is thin.** If you have any access to Indian case law, this is your unfair advantage |
| **Risk** | Needs legal annotation. The honest outcome may be "much of common law doesn't formalise" — which is a real finding but a harder sell. Pre-agree with your supervisor that a negative characterisation counts |

---

### Rank 08 — Unsat core as a principled abstention trigger
**Replacing confidence scores with certificates in high-stakes agents**

Medical-agent safety work (MedAbstain, `2601.12471`, EACL 2026) finds models often fail to abstain
when uncertain — and worse, that measured abstention is partly a **prompt artifact rather than
genuine uncertainty** (`2507.16199`). Confidence scores are the wrong instrument. A solver saying
*UNSAT, and here is the minimal conflicting set* is a **principled, inspectable** abstention trigger.

| | |
|---|---|
| **Build** | An agent whose action space includes escalate-to-human, triggered by certificate failure rather than by token probability. Evaluate on MedAgentBench write-actions (the risky ones) or a legal drafting task |
| **Measure** | Risk–coverage curves vs. confidence-based abstention. **Control for the prompt-artifact confound** |
| **Why it lands** | Unifies the lab's certificate framing with the agent-safety literature; gives abstention a semantics instead of a threshold |
| **Risk** | Only fires where the task is formalisable at all — so it's really an extension of Rank 01 or 04 rather than a standalone thesis |

---

### Quick selection guide

| If… | Pick |
|---|---|
| You want the clearest "new contribution to my supervisor's program" story | **01** |
| You want to work on the problem they explicitly called open | **02** |
| You have little compute and want a fast first publication | **03** or **06** |
| You want to connect the lab to mainstream ML/agent research | **05** |
| You have access to Indian legal data | **07** |
| You want the biggest thesis (multi-paper) | **01 → 04** as one arc, or **02 → 01** |

---

## 6. Background: the three domains

Condensed. Full detail and all sources are in the [visual briefing](https://claude.ai/code/artifact/1ba9a61f-8028-4237-a49f-18f680250b87).
Useful for related-work sections and for showing breadth in the meeting.

### 6.1 The frame that connects them

**The shared bottleneck is verification, not capability.** 2023–2025 was the capability phase —
can the model write the patch, find the case, name the diagnosis. Frontier models now clear the
static exams. 2026 is **verification under autonomy**. Each domain has a different oracle, and its
strength predicts the domain's speed:

| Domain | Oracle | Strength | Consequence |
|---|---|---|---|
| **Code** | Tests, compilers, runtime | Cheap, automatic | Fastest progress; large-scale RL possible. But **incomplete** — passing tests ≠ correct |
| **Law** | Citation to authority; adversarial process | Checkable in form, not substance | Citation *existence* nearly solved; **doctrinal correctness has no automatic checker** |
| **Medicine** | Outcome (eventually), guidelines (now) | Delayed months; ethically un-explorable | No RL on real patients → simulation → fidelity gap |

**This is exactly the argument for the lab's program.** A formal certificate is a *constructed*
oracle for domains that lack a natural one. Say it that way in the meeting.

### 6.2 Code — what to know

- **Standard pipeline:** localisation → repair → validation → selection. Survey: `2512.22256` (242 studies).
- **RL is the centre of gravity.** SWE-RM (`2512.21919`) trains an execution-free reward model:
  Qwen3-Coder-Flash 51.6% → 62.0%, Max 67.0% → 74.6% on SWE-bench Verified.
- **The benchmark revolt.** `2606.17799` argues benchmarks *collapse model, harness, and environment
  into one score*, where any component can move results by a full model generation.
  SWE-bench Pro (`2509.16941`): 1,865 tasks, **best pass@1 still 23.3%**.
  Contamination is real — models reproduce gold patches from the task ID alone.
- **Security:** indirect prompt injection succeeds **4.7% @1 attempt, 33.6% @10, 63.0% @100** (`2605.17634`).
- **The uncomfortable fact:** the METR RCT found experienced OSS developers were **19% slower** with
  early-2025 AI tools while estimating they were 20% faster.
- ⚠️ Extremely crowded. Do not compete on SWE-bench score from a university lab.

### 6.3 Law — what to know

- **Taxonomy survey:** `2601.06216`. Five practice areas; three pillars (external grounding via RAG
  and tool use; procedural orchestration; multi-layer verification modelled on firm peer review).
- **The landmark negative result:** Magesh et al., *Journal of Empirical Legal Studies* 2025
  (Stanford RegLab/HAI) — first pre-registered evaluation of commercial AI legal research tools.
  Vendors marketed RAG as "hallucination-free"; measured misleading output **~1 in 6**.
  The residual failure isn't inventing cases — it's **citing real authority that doesn't support the
  claim**, or that's been overruled.
  → *Verifying a citation exists is a lookup. Verifying it supports the claim is an open problem.*
  **This is the strongest possible motivation for the SMT approach in L4L.**
- **Benchmarks:** LegalAgentBench (`2412.17259`, 300 tasks / 17 corpora / **37 tools**, reports
  intermediate progress rate), LegalBench, LEXam, PLawBench (`2601.16669`), DLawBench (`2606.13931`),
  MASLegalBench.
- **Known weakness:** agents are **brittle under perturbation** — alter a material fact and reasoning
  often fails to adjust, implying pattern-matching over doctrine.
- **Stated gap:** jurisdictional skew, heavily Chinese. Common-law coverage thin. → Rank 07.

### 6.4 Medicine — what to know

- **AgentClinic** (`2405.07960`): reformulating static MedQA as interactive sequential encounters
  drops diagnostic accuracy to **below one-tenth** in some settings. The "LLM passes USMLE" headlines
  measured recall of a fully-specified vignette; real medicine is **information acquisition under
  uncertainty and cost**.
- **MAI-DxO / SDBench** (`2506.22405`): 304 NEJM CPC cases with **per-test dollar cost**.
  80% accuracy vs 20% generalist-physician baseline (85.5% accuracy-maximised); **−20% cost vs
  physicians, −70% vs bare o3**. *Caveats to raise yourself:* physicians had no colleagues,
  textbooks, or search; CPC cases are selected for rarity.
- **MedAgentBench** (`2501.14654`, now *NEJM AI*): FHIR-compliant virtual EHR, 300 physician-authored
  tasks, 100 patients, 700k+ data elements. Frontier models **56–72%**.
  **Key asymmetry: retrieval queries are easy; write/modify actions are hard** — which is precisely
  where a certificate-gated acceptance guard belongs.
- **Abstention:** MedAbstain (`2601.12471`) — models often fail to abstain when uncertain.
  Confound: abstention is partly a prompt artifact (`2507.16199`).
- **Automation bias:** physicians overestimated an AI's accuracy by **~30 percentage points**.
- **The unaudited assumption:** every interactive result rests on an LLM playing a cooperative,
  articulate, internally consistent patient. Real patients are none of those.

---

## 7. How to run the meeting

### Open by proving you read the paper
Restate the paradigm in one sentence — *"LLMs propose candidate artifacts, formal methods gate
acceptance with machine-checkable certificates, and formal failures become typed feedback that
drives repair"* — then name the three case studies and their three backends. This takes twenty
seconds and completely changes the conversation.

### Then make one observation
Pick the sharpest:
- *"Medicine is the missing case study, and clinical guidelines were already a model-checking target
  before LLMs — the blocker was manual formalization, which PAT-Agent solves."*
- *"Design Rule 5 gates the artifact, but nothing gates the specification. The autoformalizer is the
  only unverified component in a verification-first architecture."*
- *"Section 6's mitigation is human confirmation of the spec, but ConsistencyCheck reports experts
  miss semantic errors up to 38.5% of the time."*

### Bring three topics, not eight
- **Ambitious / new domain:** Rank 01
- **Their stated open problem:** Rank 02
- **Fast and cheap:** Rank 03 or 06

Say explicitly which is which. Supervisors respond well to a student who has already thought about
scope risk.

### Questions to ask them

1. **Is the Event-B / Lean / CSLib direction already assigned to another student?** (Wang et al. FSE
   2026 shows the group is actively expanding there — you need to know what's taken.)
2. **Do we have a clinical or legal collaborator?** This decides between Ranks 01/07 and 02/05/06.
3. **Is there a domain the group wants to enter next?** Their §7 names compliance analysis, protocol
   verification, cyber-physical safety, synthesis of critical components — medicine is conspicuously
   absent, and it's worth asking whether that's deliberate.
4. **How much of the PAT / PAT-Agent toolchain can I build on directly?** Reusing it makes Rank 01
   dramatically more feasible.
5. **Target venue and timeline?** ASE/FSE/POPL are their venues; that shapes whether you write a
   tool paper, a benchmark, or an empirical study.
6. **Do you want the auto-formalization gap attacked generally, or inside one domain?** Their §7
   implies general; a thesis is usually better inside one.

### Objections to have an answer ready for

| Objection | Answer |
|---|---|
| *"N-version formalization is already published."* | Yes — `2605.13817`, for **software requirements**, as a binary ambiguity flag. Open: statutes/guidelines as targets, risk **quantification**, and integration as an acceptance guard. Name the paper before they do |
| *"Isn't guideline formalization already done?"* | The AI-in-Medicine literature did it **manually**, and manual formalization is documented as the adoption blocker. PAT-Agent removes exactly that blocker. The two literatures have never been joined |
| *"Will formal methods scale to real clinical text?"* | Probably not fully — which is why the honest scope is a narrow, well-structured guideline first, and why coverage is a reported metric rather than an assumption |
| *"Do benchmark numbers matter?"* | The METR RCT says not automatically. That's an argument for certificate-based and human-facing evaluation (Rank 03), not against the field |

---

## 8. Bibliography

### 8.1 The group's own work — read all of these first

| Ref | Work | Venue |
|---|---|---|
| — | **Synergizing LLMs and Formal Methods for Neural-Symbolic Reasoning** — Dong, Cai, Hou, Sun, Wang, Zhang, Zuo | J. ACM 2025 · [OpenReview](https://openreview.net/forum?id=wkisIZbntD) · *the PDF in this folder* |
| [`2511.21033`](https://arxiv.org/abs/2511.21033) | **Towards Trustworthy Legal AI through LLM Agents and Formal Reasoning** (L4L) — Chen, Cai, Hou, Dong | Case study 1. Four stages: statute knowledge building → dual fact/statute extraction → solver-centric adjudication → judicial rendering |
| — | **PAT-Agent: Autoformalization for Model Checking** — Zuo, Zhang, Wang, Cai, Hou, Sun, Dong | **ASE 2025**, pp. 2122–2133. Case study 2 |
| — | **Automated Program Refinement: Guide and Verify Code LLM with Refinement Calculus** — Cai, Hou, Sanan, Luan, Lin, Sun, Dong | **POPL 2025**. Case study 3 |
| [`2605.17475`](https://arxiv.org/abs/2605.17475) | **Event-B Agent: LLM Agent for Formal Model Synthesis and Repair** — Wang, Zuo, Sun, Li, Ait Ameur, Dong | **FSE 2026**. The group's newest direction |
| — | **PAT: Towards Flexible Verification under Fairness** — Sun, Liu, Dong, Pang | CAV 2009. The underlying toolkit |

### 8.2 Foundations they build on

| Ref | Work |
|---|---|
| [`2401.11817`](https://arxiv.org/abs/2401.11817) | Xu, Jain, Kankanhalli — **Hallucination is Inevitable: An Innate Limitation of LLMs**. *The paper's philosophical premise* |
| [`2405.06624`](https://arxiv.org/abs/2405.06624) | Dalrymple et al. — Towards Guaranteed Safe AI |
| — | Wing — **Trustworthy AI**, CACM 64(10), 2021 |
| — | de Moura & Bjørner — **Z3: An Efficient SMT Solver**, TACAS 2008 |
| — | Morgan — **Programming from Specifications**, 1990. *The refinement calculus behind case study 3* |
| — | Hoare — **Communicating Sequential Processes**, CACM 1978. *CSP# ancestor* |
| [`2602.04846`](https://arxiv.org/abs/2602.04846) | Barrett et al. — **CSLib: The Lean Computer Science Library**. Flagged in their future work |
| — | Yang et al. — **LeanDojo**, NeurIPS 2023. Their example of *tight* integration |
| — | Li, Huang, Naik — **Scallop**, PLDI 2023 |
| — | Riegel et al. — **Logical Neural Networks**, `arXiv:2006.13155` |
| — | Pan et al. — **Logic-LM**, EMNLP Findings 2023 |

### 8.3 Autoformalization fidelity — the Rank 02 related-work core

| ID | Work | Why it matters |
|---|---|---|
| [`2605.13817`](https://arxiv.org/html/2605.13817v1) | Neurosymbolic Auditing of Natural-Language Software Requirements | ⚠️ **N-version SMT-equivalence, already published.** Cite and differentiate |
| [`2605.26457`](https://arxiv.org/pdf/2605.26457) | Verus-SpecGym: Agentic Environment for Evaluating Specification Autoformalization | Spec autoformalization is a **distinct bottleneck** from code generation |
| [`2604.25031`](https://arxiv.org/html/2604.25031v1) | Faithful Autoformalization via Roundtrip Verification and Repair | Their round-trip idea, implemented |
| [`2511.12784`](https://arxiv.org/pdf/2511.12784) | Evaluating Autoformalization Robustness via Semantically Similar Paraphrasing | Paraphrase-invariance as fidelity test |
| [`2510.24592`](https://arxiv.org/pdf/2510.24592) | ReForm: Reflective Autoformalization | Prospective bounded sequence optimization |
| [`2511.11829`](https://arxiv.org/abs/2511.11829) | Towards Autoformalization of LLM-generated Outputs for Requirement Verification | Closest SE-requirements framing |
| [`2606.29493`](https://arxiv.org/pdf/2606.29493) | Faults in Our Formal Benchmarking | Dataset defects in Lean benchmarks |
| [`2506.10903`](https://arxiv.org/pdf/2506.10903) | Beyond Gold Standards: Epistemic Ensemble of LLM Judges for Formal Mathematical Reasoning | Ensemble judging |
| — | **ConsistencyCheck** | 859 expert-annotated items; **experts make semantic errors up to 38.5%** of the time |

### 8.4 Agent safety, specification, enforcement — Rank 04 core

| ID | Work |
|---|---|
| [`2608.14590`](https://arxiv.org/html/2608.14590) | Toward Safe LLM Agents: A Survey of Specification, Verification, and Enforcement (38 studies, 2022–2026) |
| [`2607.02599`](https://arxiv.org/pdf/2607.02599) | AgentLTL: Trace Verification for Procedural Compliance in Tool-Using Agents |
| [`2508.03665`](https://arxiv.org/pdf/2508.03665) | A Design-by-Contract-Inspired Neurosymbolic Layer for Trustworthy Agent Design |
| [`2511.09008`](https://arxiv.org/abs/2511.09008) | A Neurosymbolic Approach to Natural Language Formalization and Verification |
| [`2510.16381`](https://arxiv.org/pdf/2510.16381) | ATA: Neuro-Symbolic Autonomous and Trustworthy Agents |
| [`2605.10325`](https://arxiv.org/html/2605.10325v1) | Verifiable Process Rewards for Agentic Reasoning |

### 8.5 Legal

| ID | Work |
|---|---|
| [JELS 2025](https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413) | Magesh et al. — **Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools.** *The anchor negative result* |
| [`2601.06216`](https://arxiv.org/html/2601.06216v1) | LLM Agents in Law: Taxonomy, Applications, Challenges |
| [`2509.00710`](https://arxiv.org/pdf/2509.00710) | On Verifiable Legal Reasoning: Multi-Agent Framework with Formalized Knowledge Representations. **Check overlap with L4L** |
| [`2412.17259`](https://arxiv.org/abs/2412.17259) | LegalAgentBench — 300 tasks, 17 corpora, 37 tools, **reports intermediate progress rate** |
| [`2605.21071`](https://arxiv.org/pdf/2605.21071) | Fine-grained Claim-level RAG Benchmark for Law |
| [`2505.03970`](https://arxiv.org/abs/2505.03970) | A Reasoning-Focused Legal Retrieval Benchmark |
| [`2504.01840`](https://arxiv.org/pdf/2504.01840) | LRAGE: Legal RAG Evaluation Tool |
| [`2606.30906`](https://arxiv.org/pdf/2606.30906) | Investigating Multi-Agent Deliberation in Law |
| [`2602.12056`](https://arxiv.org/pdf/2602.12056) | LawThinker: Deep Research Legal Agent |

### 8.6 Medical — Rank 01 core

| ID | Work |
|---|---|
| — | **Adopting model checking techniques for clinical guidelines verification** — *Artificial Intelligence in Medicine* (Elsevier) |
| — | **Using model checking for critiquing based on clinical guidelines** — *Artificial Intelligence in Medicine*, 2008 |
| — | Analyzing Clinical Practice Guidelines Using a Decidable Metric Interval-Based Temporal Logic — Springer |
| [PMC3197986](https://pmc.ncbi.nlm.nih.gov/articles/PMC3197986/) | Computerization of workflows, guidelines, and care pathways: implementation challenges. **Documents manual formalization as the blocker** |
| [`2405.07960`](https://arxiv.org/abs/2405.07960) | AgentClinic — accuracy collapse from static to sequential |
| [`2506.22405`](https://arxiv.org/abs/2506.22405) | Sequential Diagnosis with Language Models (SDBench / MAI-DxO) |
| [`2501.14654`](https://arxiv.org/abs/2501.14654) | MedAgentBench — FHIR virtual EHR, now *NEJM AI* |
| [`2601.12471`](https://arxiv.org/abs/2601.12471) | Knowing When to Abstain: Medical LLMs Under Clinical Uncertainty (EACL 2026) |
| [`2507.16199`](https://arxiv.org/abs/2507.16199) | LLM Abstention Can Be a Prompt Artifact. **The confound to control for** |
| [`2607.07761`](https://arxiv.org/abs/2607.07761) | Aligning Clinical Needs and AI Capabilities: Survey on LLMs for Medical Reasoning |

### 8.7 Code agents — Rank 05/06 context

| ID | Work |
|---|---|
| [`2512.22256`](https://arxiv.org/abs/2512.22256) | Agentic Software Issue Resolution with LLMs: A Survey (242 studies) |
| [`2512.21919`](https://arxiv.org/abs/2512.21919) | SWE-RM: Execution-free Feedback for SWE Agents |
| [`2604.14820`](https://arxiv.org/abs/2604.14820) | SWE-TRACE: Rubric Process Reward Models + Test-Time Scaling |
| [`2606.17799`](https://arxiv.org/abs/2606.17799) | Position: Coding Benchmarks Are Misaligned with Agentic SE |
| [`2509.16941`](https://arxiv.org/abs/2509.16941) | SWE-Bench Pro — best pass@1 23.3% |
| [`2605.17634`](https://arxiv.org/html/2605.17634) | AI Agents May Always Fall for Prompt Injections |
| [metr.org](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) | METR RCT — 19% slower, perceived 20% faster |

### 8.8 Human factors — Rank 03 core

| ID | Work |
|---|---|
| [`2502.13321`](https://arxiv.org/pdf/2502.13321) | Adjust for Trust: Mitigating Trust-Induced Inappropriate Reliance on AI Assistance |
| [`2510.26518`](https://arxiv.org/pdf/2510.26518) | Human-AI Complementarity: A Goal for Amplified Oversight |
| [PMC11612524](https://pmc.ncbi.nlm.nih.gov/articles/PMC11612524/) | Facilitating Trust Calibration in AI-Driven Diagnostic Decision Support — physicians overestimated accuracy by ~30 points |

---

*Sources are the PDF in this folder, public arXiv preprints, and peer-reviewed articles located by
literature search. Reported figures are as stated by their authors and have not been independently
reproduced.*
