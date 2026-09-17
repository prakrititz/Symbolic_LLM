# FormalLLM

**DISCLAIMER: This project is not an original work. It is a completely personal, independent implementation of the architecture described in the paper "Automated Program Refinement: Guide and Verify Code Large Language Model with Refinement Calculus" (Refine4LLM).** 

All core theoretical concepts, refinement laws, the $L_{spec}$ specification language, and the verification loop architectures are derived entirely from the original authors' research.

## Overview
FormalLLM is an implementation of a neuro-symbolic refinement engine. It mathematically bridges the gap between Large Language Models (LLMs) and formal methods (Refinement Calculus) to generate provably correct code. 

Instead of relying on an LLM to generate an entire correct program at once, FormalLLM breaks the problem down into a tree of smaller, mathematically verifiable sub-specifications.

## Architecture

```mermaid
flowchart TD

subgraph group_front["Specification Front End"]
  node_parser["L_spec parser<br/>Lark parser<br/>[parser.py]"]
  node_grammar["L_spec grammar<br/>Lark grammar<br/>[grammar.lark]"]
  node_spec_ast["Specification AST<br/>formula model<br/>[ast.py]"]
end

subgraph group_refinement["Refinement Core"]
  node_engine["Refinement engine<br/>orchestrator<br/>[engine.py]"]
  node_refinement_graph["Refinement graph<br/>search state<br/>[graph.py]"]
  node_frame["Refinement frames<br/>context state<br/>[frame.py]"]
  node_laws["Refinement laws<br/>law registry<br/>[registry.py]"]
end

subgraph group_guidance["LLM Control"]
  node_agent["Refinement agent<br/>control loop<br/>[refiner.py]"]
  node_provider["LLM provider<br/>model abstraction<br/>[provider.py]"]
  node_response_parser["LLM response parser<br/>structured output<br/>[parser.py]"]
end

subgraph group_validation["Verification &amp; Execution"]
  node_proof_obligations["Proof obligations<br/>verification model"]
  node_z3_translator["Z3 translator<br/>formula lowering<br/>[z3_translator.py]"]
  node_z3_backend{{"Z3 backend<br/>theorem prover<br/>[z3_backend.py]"}}
  node_program_ast["Program AST<br/>LPL model<br/>[ast.py]"]
  node_python_lowering["Python lowering<br/>code generator<br/>[to_python.py]"]
  node_runner["Generated-code runner<br/>execution boundary<br/>[runner.py]"]
  node_trace["Trace serializer<br/>run records<br/>[serializer.py]"]
end

subgraph group_experiments["Entrypoints &amp; Benchmarks"]
  node_main["Interactive entrypoint<br/>Python CLI<br/>[main.py]"]
  node_benchmark["Benchmark harness<br/>Python runner<br/>[benchmark.py]"]
  node_bench_run["Benchmark launcher<br/>Python runner<br/>[run_bench.py]"]
end

node_main -->|"accepts specifications"| node_parser
node_main -->|"starts refinement"| node_agent
node_benchmark -->|"runs cases"| node_agent
node_bench_run -->|"launches"| node_benchmark
node_grammar -->|"defines syntax"| node_parser
node_parser -->|"builds"| node_spec_ast
node_agent -->|"requests law choice"| node_provider
node_provider -->|"returns response"| node_response_parser
node_response_parser -->|"selected law and parameters"| node_engine
node_spec_ast -->|"refines"| node_engine
node_engine -->|"updates search state"| node_refinement_graph
node_engine -->|"propagates context"| node_frame
node_engine -->|"applies"| node_laws
node_laws -->|"generates"| node_proof_obligations
node_laws -->|"constructs"| node_program_ast
node_proof_obligations -->|"contains formulas"| node_z3_translator
node_z3_translator -->|"submits formulas"| node_z3_backend
node_z3_backend -->|"gates transitions"| node_engine
node_z3_backend -.->|"failure feedback"| node_agent
node_program_ast -->|"lowers"| node_python_lowering
node_python_lowering -->|"generated Python"| node_runner
node_engine -->|"serializes activity"| node_trace
node_runner -->|"serializes execution results"| node_trace
node_trace -->|"benchmark records"| node_benchmark

click node_main "https://github.com/prakrititz/symbolic_llm/blob/main/main.py"
click node_benchmark "https://github.com/prakrititz/symbolic_llm/blob/main/benchmark.py"
click node_bench_run "https://github.com/prakrititz/symbolic_llm/blob/main/benchmarks/run_bench.py"
click node_parser "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lspec/parser.py"
click node_grammar "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lspec/grammar.lark"
click node_spec_ast "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lspec/ast.py"
click node_agent "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/agent/refiner.py"
click node_provider "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/llm/provider.py"
click node_response_parser "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/llm/parser.py"
click node_engine "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/refinement/engine.py"
click node_refinement_graph "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/refinement/graph/graph.py"
click node_frame "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/refinement/frame.py"
click node_laws "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/refinement/laws/registry.py"
click node_proof_obligations "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/verification/proof_obligations.py"
click node_z3_translator "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lspec/z3_translator.py"
click node_z3_backend "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/verification/z3_backend.py"
click node_program_ast "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lpl/ast.py"
click node_python_lowering "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/lpl/to_python.py"
click node_runner "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/execution/runner.py"
click node_trace "https://github.com/prakrititz/symbolic_llm/blob/main/FormalLLM/trace/serializer.py"

classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a
class node_parser,node_grammar,node_spec_ast toneBlue
class node_engine,node_refinement_graph,node_frame,node_laws toneAmber
class node_agent,node_provider,node_response_parser toneMint
class node_proof_obligations,node_z3_translator,node_z3_backend,node_program_ast,node_python_lowering,node_runner,node_trace toneRose
class node_main,node_benchmark,node_bench_run toneIndigo
```

1. **L_spec Parser**: A Lark-based grammar parser that converts textual mathematical preconditions and postconditions into an Abstract Syntax Tree (AST).
2. **Refinement Calculus Engine**:
   - Implements strict refinement laws (Assignment, Sequential Composition, Alternation, Iteration, and Skip).
   - Handles capture-avoidant substitution (alpha-renaming) for quantified variables during refinement steps.
3. **Z3 Verification Backend**: Translates the AST's proof obligations into `z3-solver` constraints. It provides deterministic feedback (`PROVED`, `FAILED` with counterexamples, or `UNKNOWN`).
4. **LLM-Guided Automated Refiner**:
   - An intelligent agent loop that dynamically prompts an LLM with the current refinement state.
   - Evaluates the LLM's chosen law and parameters.
   - Implements a **Counterexample-Guided Feedback Loop** (feeding Z3 failures back into the LLM prompt).
   - Features a robust recursive backtracking/fallback mechanism if the LLM leads the refinement down an unprovable path.

## Benchmarking
The `benchmarks/` directory contains an extensive test suite used to evaluate how well different local LLMs (like Llama 3.1, Qwen 3.5) navigate the formal refinement process.

- **Tier A**: Single terminal laws (e.g., trivially implied postconditions or direct assignments).
- **Tier B**: Structural decompositions (e.g., sequential composition or alternation).
- **Tier C**: Complex, nonlinear problems from the original paper (e.g., tight square root bounds or proper loop invariants).

To reproduce the benchmark runs:
```bash
python benchmarks/run_bench.py --configs llama3.1 qwen3.5-think --laws all
```
The results are output in JSON Lines format and can be analyzed using `benchmarks/analyse.py`.

## Dependencies
- Python 3.10+
- `lark` (for parsing $L_{spec}$)
- `z3-solver` (for automated theorem proving)
- `pytest` (for running the validation suites)

## Installation & Testing

```bash
pip install -r requirements.txt
python -m pytest FormalLLM/tests/
```

## Citation & Attribution
This implementation studies and reproduces the mechanics of:
> **Automated Program Refinement: Guide and Verify Code Large Language Model with Refinement Calculus (Refine4LLM)**
> *(Please refer to the original publication for the full theoretical proofs, completeness guarantees, and algorithmic definitions).*
