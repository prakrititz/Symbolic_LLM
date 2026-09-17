### Both arms, per model

| Model | Direct: tests passed | Direct verdict | Refinement (v1) | Refinement (v2, escaping fixed) |
|---|---|---|---|---|
| `oracle` | -- | -- (cannot write code) | PASS | PASS |
| `gpt-oss-120b` | 12/12 | PASS | EXHAUSTED | BUDGET |
| `qwen3-coder-next` | 12/12 | PASS | BUDGET | EXHAUSTED |
| `llama3.1` | 9/12 | 9/12 | EXHAUSTED | EXHAUSTED |
| `qwen3.5-nothink` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |
| `qwen3.5-think` | 0/12 | does not run | ERROR | EXHAUSTED |
| `ornith` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |
| `ornith-think` | 12/12 | PASS | EXHAUSTED | EXHAUSTED |

### Refinement arm detail

| Model | v1 outcome | v1 calls | v2 outcome | v2 calls | v2 laws accepted |
|---|---|---|---|---|---|
| `oracle` | SUCCESS | 4 | SUCCESS | 4 | {'sequential': 1, 'assignment': 2, 'iteration': 1} |
| `gpt-oss-120b` | EXHAUSTED | 12 | BUDGET | 15 | {'sequential': 1, 'assignment': 1, 'strengthen_post': 2, 'weaken_pre': 1} |
| `qwen3-coder-next` | BUDGET | 15 | EXHAUSTED | 15 | {'alternation': 1} |
| `llama3.1` | EXHAUSTED | 8 | EXHAUSTED | 15 | {'sequential': 1, 'alternation': 1} |
| `qwen3.5-nothink` | EXHAUSTED | 4 | EXHAUSTED | 4 | {} |
| `qwen3.5-think` | ERROR | 3 | EXHAUSTED | 4 | {} |
| `ornith` | EXHAUSTED | 4 | EXHAUSTED | 4 | {} |
| `ornith-think` | EXHAUSTED | 4 | EXHAUSTED | 4 | {} |

Direct arm passing all 12 inputs: 5/7
Refinement arm (v1) passing: 1/8
Refinement arm (v2) passing: 0/7
