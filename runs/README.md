# runs/

One folder per agent iteration: `runs/<YYYY-MM-DD>-<short-name>/`. Its `README.md` describes what was tried, the model, tokens and cost, and the result, with the raw data next to it.

## Front matter

Every run `README.md` starts with a short front matter block. It feeds the generated ledger in [`index.json`](index.json), the table in [`PROGRESS.md`](../PROGRESS.md) and the one in [`notes/agent-brief.md`](../notes/agent-brief.md).

```yaml
---
title: Blocked record permutation probe
date: 2026-11-12 16:48                      # the UTC time is optional
verdict: failed
summary: One or two plain sentences for humans: what was learned and, if it failed, why.
model: agent:gpt-6 (Codex)
idea: 3. Payload permutation for records   # optional: the idea in notes/ideas.md
result: 0.542–0.648×                        # optional: the headline number
baseline: fastest measured reference        # optional: what the result is compared with
closes: [tile-and-sort payload permutation] # optional: lines of work this run closes
opens: [prefetch gather as the control]     # optional: lines of work this run opens
cost: not captured                          # optional: tokens and money, or "not captured"
---
```

`title`, `date`, `verdict`, `summary` and `model` are required. Values are plain text on one line. Add a UTC time to `date` when several runs share a day, so they stay in order. Lists use `[a, b]`. Text after ` #` is a comment.

| Verdict | Meaning |
|---|---|
| `works` | Met the project's success threshold on the declared workload, on fresh inputs. |
| `promising` | A measured gain that needs more evidence (real data, more references, other conditions). |
| `failed` | Fell short of its preregistered threshold. The line it tested is closed or must change. |
| `inconclusive` | Could not decide: noise, a bug, missing references or an interrupted run. |
| `diagnostic` | Measured a bound, a cost or headroom to decide what to try next. It does not test a candidate. |
| `setup` | Infrastructure, smoke tests or project organisation. No research result. |

After adding or editing a run, run `python scripts/build_progress.py`. CI fails if a front matter block is invalid or the generated files are stale.
