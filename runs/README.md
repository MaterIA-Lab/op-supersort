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
speedup: 0.542–0.648                        # optional: best reference time ÷ candidate time (>1 = faster)
estimate: false                             # optional: true when speedup is estimated headroom, not a measured candidate
how: After sorting, split the output into tiles that fit in the L2 cache and move the records tile by tile.
compared_with: The fastest measured reference, including a plain gather with software prefetch.
faster_where: Slower in every case (0.54–0.65×). Sorting the requests cost more than the better locality saved.
title_es: Permutación de registros por bloques
how_es: Tras ordenar, dividir la salida en bloques que caben en la caché L2 y mover los registros bloque a bloque.
compared_with_es: La referencia más rápida medida, incluido un gather simple con prefetch por software.
faster_where_es: Más lento en todos los casos (0,54–0,65×). Ordenar las peticiones costó más de lo que ahorró la localidad.
---
```

`title`, `date`, `verdict`, `summary` and `model` are required.

`how`, `compared_with` and `faster_where` are also required for every verdict except `setup`. They are shown, as written, in the run log on the project's page of the [OpenPrototypes website](https://openprototypes.materiacore.com), where anyone can click a run to read them. Write them for a curious non-expert:

- `how`: how the idea was supposed to work, in one to three plain sentences. Explain any term a non-expert would not know.
- `compared_with`: what it raced against (the strongest references and controls), in plain words.
- `faster_where`: where it was faster, where it was not, and by how much. Name the conditions behind every number.
- `speedup`: the headline ratio as `time of the best reference ÷ time of the candidate`, a single number or a `low–high` range. Leave it out when nothing comparable was timed. Set `estimate: true` when it is a headroom estimate rather than a measured candidate.
- Spanish versions use the same keys with `_es` (`title_es`, `how_es`, `compared_with_es`, `faster_where_es`). The Spanish page falls back to English when they are missing.

Values are plain text on one line. Add a UTC time to `date` when several runs share a day, so they stay in order. Lists use `[a, b]`. Text after ` #` is a comment, so do not write ` #` inside a value.

| Verdict | Meaning |
|---|---|
| `works` | Met the project's success threshold on the declared workload, on fresh inputs. |
| `promising` | A measured gain that needs more evidence (real data, more references, other conditions). |
| `failed` | Fell short of its preregistered threshold. The line it tested is closed or must change. |
| `inconclusive` | Could not decide: noise, a bug, missing references or an interrupted run. |
| `diagnostic` | Measured a bound, a cost or headroom to decide what to try next. It does not test a candidate. |
| `setup` | Infrastructure, smoke tests or project organisation. No research result. |

After adding or editing a run, run `python scripts/build_progress.py`. CI fails if a front matter block is invalid or the generated files are stale.

## Check the published measurements

These commands regenerate the tables from the tracked CSVs without running the benchmarks. Run them from the repository root with Python 3. Each run's README links its protocol, raw data, metadata and full reproduction commands. The metadata records the source commit used for each measurement.

```sh
python runs/2026-11-12-record-permutation/analyze.py runs/2026-11-12-record-permutation/raw.csv
python runs/2026-11-12-record-permutation/analyze.py runs/2026-11-12-blocked-permutation/raw.csv --blocked-probe
python runs/2026-11-12-page-remapped-merge/analyze.py runs/2026-11-12-page-remapped-merge
python runs/2026-11-12-page-remapped-merge/analyze.py runs/2026-11-12-page-remapped-merge-candidate --candidate
python -X utf8 runs/2026-11-12-gharchive-page-coverage/probe.py --report runs/2026-11-12-gharchive-page-coverage/coverage.csv
python -X utf8 runs/2026-11-12-gharchive-disjoint-merge/analyze.py runs/2026-11-12-gharchive-disjoint-merge/disjoint.csv
python -X utf8 runs/2026-11-15-compressed-key-bandwidth/analyze.py runs/2026-11-15-compressed-key-bandwidth/raw.csv
python -X utf8 runs/2026-11-15-smt-gather-helper/analyze.py runs/2026-11-15-smt-gather-helper/raw.csv
python -X utf8 runs/2026-11-22-bitplane-sort/analyze.py runs/2026-11-22-bitplane-sort/raw.csv
python -X utf8 runs/2026-11-22-checkpoint-cycles/analyze.py runs/2026-11-22-checkpoint-cycles/raw.csv
python -X utf8 runs/2026-11-23-key-correction-spans/analyze.py holdout runs/2026-11-23-key-correction-spans/holdout.csv
python -X utf8 runs/2026-11-23-key-correction-spans/analyze.py reference-audit runs/2026-11-23-key-correction-spans/reference-audit.csv
python -X utf8 runs/2026-11-23-flight-key-corrections/analyze.py
python -X utf8 runs/2026-11-16-linux-producer-placement/analyze.py \
  runs/2026-11-16-linux-producer-placement/runner-1.csv \
  runs/2026-11-16-linux-producer-placement/runner-2.csv
```
