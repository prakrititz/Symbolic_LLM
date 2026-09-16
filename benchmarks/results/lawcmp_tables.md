# Core laws (5) vs Extended laws (9)

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

## Programs found in the extended arm


**llama3.1 / A2-assign**
```
x = (N + 1)
```

**qwen3.5-nothink / A1-skip**
```
pass
```

**qwen3.5-nothink / A2-assign**
```
x = (N + 1)
```
