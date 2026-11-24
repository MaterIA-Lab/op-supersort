---
title: Sorting repeated keys together across exception gaps
date: 2026-11-24 16:16
verdict: failed
summary: A mask grouped nearby equal keys despite interruptions, but the fixed blocks produced more tags than exact runs on the four main inputs. The full sort reached 1.004-1.086× against the run-based reference.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 13. Sort repeated keys together across short exception gaps
result: 1.004-1.086× on four primary comparisons
baseline: Fastest verified median of per-row and contiguous equal-key run tags with VQSort and stable byte radix
closes: [single sampled key in each 64-row block for the registered sort]
speedup: 1.004-1.086
how: In each group of up to 64 rows, give nearby repeats of one key a single sortable tag and store which positions it covers. Give exceptional rows their own tags. After sorting the tags, write the full records in order.
compared_with: Sorting one tag per row and sorting one tag per consecutive run of equal keys. Each method uses the same two sorters and copies full records only into the final output.
faster_where: With 32 and 128 MiB of records and one independent key replacement per eight rows on average, the mask ran 1.004-1.086 times as fast as the best reference. It reached 1.132-1.138 times as fast in the 32 MiB control with one replacement per four rows.
title_es: Agrupar claves repetidas aunque haya excepciones intercaladas
how_es: En cada bloque de hasta 64 filas, se asigna una sola ficha a las repeticiones de una clave y se guarda a qué posiciones corresponde. Las filas con claves distintas conservan sus propias fichas. Después se escriben los registros completos en orden.
compared_with_es: Ordenar una ficha por fila y ordenar una ficha por tramo consecutivo de claves iguales. Cada método usa las mismas dos técnicas de ordenación y copia los registros completos al resultado final.
faster_where_es: Con 32 y 128 MiB de registros y una clave reemplazada al azar de cada ocho de media, la máscara rindió entre 1,004× y 1,086× frente a la mejor referencia. En el control de 32 MiB con una de cada cuatro claves reemplazadas, alcanzó entre 1,132× y 1,138×.
---

# Sorting repeated keys together across exception gaps

**Decision. Close the fixed-block single-key mask on the tested inputs.**
Both mask variants missed the 77% time gate in all four primary cases.
The exact equal-key runs were the strongest reference. The holdout
was conditional on a passing development screen.
[Registered protocol](protocol.md) · [Prototype and reproduction](../../prototypes/agents/exception-mask-sort/README.md)

## Timings

Every method stably sorts 64-byte records with a parallel uint32
key column into a reused output buffer. Timing covers scratch
allocation and release, preparation, sorting, copying all rows
and the final fence. Each number is the median of seven calls
after two warm-ups. The ratio divides the fastest reference
median by the mask with VQSort.

| Input | Shape | Seed | Best reference | Reference, ms | Mask with VQSort, ms | Mask with radix, ms | Ratio |
|---|---|---:|---|---:|---:|---:|---:|
| 32 MiB | Burst, 1/8 replacements | 39281 | Runs with VQSort | 6.619 | 6.097 | 6.611 | 1.086× |
| 32 MiB | Burst, 1/8 replacements | 87407 | Runs with VQSort | 6.630 | 6.604 | 6.812 | 1.004× |
| 128 MiB | Burst, 1/8 replacements | 39281 | Runs with VQSort | 27.643 | 25.462 | 27.727 | 1.086× |
| 128 MiB | Burst, 1/8 replacements | 87407 | Runs with VQSort | 30.684 | 28.428 | 29.828 | 1.079× |
| 32 MiB | Burst, no replacements | 39281 | Runs with VQSort | 3.471 | 4.606 | 4.627 | 0.754× |
| 32 MiB | Burst, no replacements | 87407 | Runs with radix | 3.484 | 4.192 | 4.608 | 0.831× |
| 32 MiB | Burst, 1/4 replacements | 39281 | Runs with VQSort | 9.407 | 8.310 | 9.647 | 1.132× |
| 32 MiB | Burst, 1/4 replacements | 87407 | Runs with VQSort | 9.147 | 8.041 | 8.995 | 1.138× |
| 32 MiB | Independent uniform keys | 39281 | Rows with VQSort | 11.267 | 13.485 | 15.535 | 0.836× |
| 32 MiB | Independent uniform keys | 87407 | Rows with VQSort | 11.225 | 12.877 | 14.059 | 0.872× |

In the primary cases the best run reference was 1.547-1.622×
as fast as the fastest per-row tag method. It used about 24% as
many tags. The sampled mask produced 9.0-10.1% more tags than
the run reference. The blocks split long same-key stretches and
can mix two source bursts or sample an exceptional key. In the
quarter-replacement control the mask produced about 2% fewer
tags than runs and reduced preparation time. The output used
the same coalesced source spans for all six methods.
[Raw samples and phase timings](development.csv)

## Geometry and remaining budget

After the screen, an independent geometry audit regenerated
the primary keys and reproduced all four sampled tag counts.
It also counted the best possible choices of one or two keys
per fixed block. The sampled two-key count uses one choice
from each half and counts their combined matches over the full
block. These numbers describe the information to sort.

| Input | Seed | Exact runs | Sampled one key | Best one key | Sampled two keys | Best two keys | Prepare and sort budget, ms | Measured, ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 MiB | 39281 | 125,249 | 136,518 | 112,928 | 90,051 | 76,584 | 1.473 | 2.416 |
| 32 MiB | 87407 | 124,487 | 137,005 | 111,330 | 89,677 | 76,161 | 1.021 | 2.410 |
| 128 MiB | 39281 | 499,845 | 547,382 | 448,430 | 359,778 | 305,643 | 5.301 | 9.200 |
| 128 MiB | 87407 | 499,497 | 545,394 | 446,705 | 359,930 | 305,353 | 6.319 | 9.998 |

Output copying took 59-63% of the mask variant's median wall
time on the main cases. Subtracting its measured output median
from 77% of the reference time leaves the displayed budget for
preparation and sorting. This optimistic diagnostic combines
phase medians and omits final release overhead. Keeping the output
cost would require cutting the combined planning and sorting
medians by 37-58%. Two sampled keys would remove about 34-35%
of the tags, with added encoder work. That gap favors a new
mechanism that also addresses the record copy cost. The two-key
counts come from a geometry analysis without execution timings.
[Reproducible tag count audit](geometry.py)

## Verification and accounting

- All 420 measured calls and 120 warm-ups matched the entire
  stable output from a separate `std::stable_sort` of source
  indexes. All six methods also passed 90 fixtures covering
  equal keys, unsigned boundaries, partial blocks and ties
  across group and ordinary tags. [Verification](verification.txt)
- AMD Ryzen 7 5800X, Windows 11, one thread pinned to logical
  CPU 8, GCC 16.1.0, and pinned Highway VQSort. Both key and
  record arrays and the output were flushed before every call.
  The evidence covers synthetic bursts, a supplied key column
  and full materialization. [Build and environment](development-metadata.json)
- For the primary VQSort comparisons, the run encoder requested
  1.50 or 6.00 MiB of heap capacity for tags and boundaries.
  The mask requested 2.06 or 8.25 MiB for tags and masks.
  These capacities exclude allocator overhead, temporary
  growth overlap, the common input and output, and sorter stack.
- Model `gpt-6.2-sol`. External paid compute spend was zero.
  Model tokens, reasoning setting and session cost were not captured.

```powershell
python -X utf8 runs/2026-11-24-exception-mask-sort/analyze.py development
python -X utf8 runs/2026-11-24-exception-mask-sort/geometry.py
```
