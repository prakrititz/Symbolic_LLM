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
