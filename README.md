# FormalLLM

FormalLLM is a framework for Automated Program Refinement guided and verified by Large Language Models with Refinement Calculus.

## L_spec Parser
We currently have implemented the `L_spec` formal specification language parser.
It supports parsing conditions, quantified expressions, and translates them directly into `z3-solver` expressions for automated theorem proving.

### Installation

```bash
pip install -r FormalLLM/requirements.txt
```

### Testing

```bash
python -m pytest FormalLLM/tests
```
