---
title: Page-remapped merge candidate
date: 2026-11-12 17:33
verdict: promising
idea: 1. Virtual memory as a data-movement engine
summary: Mapping aligned input pages into the output beat the best fresh-output merge of two sorted runs of 128-byte records by 1.33–1.36×, and by 2.67× when 75% of the output was mapped. It lost to a merge into an already-touched buffer (0.36–0.74×) and regressed on bursty and interleaved runs (0.82–0.86×). Synthetic data only.
result: 1.326–2.668× on edge-overlap runs (2/4 cases ≥1.3×, 0/4 ≥1.5× on both seeds)
baseline: fastest merge into a fresh output
opens: [frequency of mappable pages in real sorted batches]
model: OpenAI GPT-6.1 Sol, Extra High
cost: not captured
speedup: 1.326–2.668
how: The real implementation: walk the merge, map every page-aligned stretch of at least 64 KiB into the output, and copy the leftovers. The caller sees an ordinary contiguous, read-only array.
compared_with: The fastest merge into a fresh output (plain, galloping bulk copy, and a hybrid). Also, separately, a merge into an output buffer that already exists in memory.
faster_where: 1.33–1.36× faster on runs that overlap at the edges, and 2.67× when 75% of the output can be mapped. Slower than writing into a buffer that is already in memory (0.36–0.74×), and slower on bursty or interleaved runs (0.82–0.86×). Synthetic data only.
title_es: Candidato de mezcla con remapeo de páginas
how_es: La implementación real: recorrer la mezcla, mapear en la salida cada tramo alineado a página de al menos 64 KiB y copiar el resto. Quien la usa ve un array normal, contiguo y de solo lectura.
compared_with_es: La mezcla más rápida hacia una salida nueva (clásica, galopante con copia en bloque e híbrida). Y, aparte, una mezcla hacia un buffer de salida que ya está en memoria.
faster_where_es: 1,33–1,36× más rápido con tramos que se solapan en los extremos, y 2,67× cuando se puede mapear el 75 % de la salida. Más lento que escribir en un buffer que ya está en memoria (0,36–0,74×) y con tramos a ráfagas o intercalados (0,82–0,86×). Solo datos sintéticos.
---

# Page-remapped merge candidate — 2026-11-12

- **Model** OpenAI GPT-6.1 Sol, Extra High, as identified by the owner. Exact token count and billed model cost are unavailable in the session. Local WSL compute has no incremental cloud charges.
- **State** Complete. Two non-control cases cleared 1.3× on both seeds for fresh output. See [summary](summary.md), [raw samples](candidate.csv) and [machine metadata](metadata.txt).

## Candidate and controls

Reuse the pilot's maximal-slice traversal. For each slice, map its maximal full-page interior into the reserved contiguous destination if the offsets are congruent and the interior contains at least 64 KiB. This is the smallest profitable extent band in the pilot. Copy any leading and trailing records and copy a slice in full if it is too short or misaligned. The output aliases immutable source pages and presents the same read-only contiguous interface as the references.

The primary comparison uses the fastest of three references for fresh output: the pilot's scalar and galloping bulk merges, and a hybrid that copies the non-overlapping prefix and suffix in bulk and merges the overlapping middle with a two-finger loop. Apply the same `mprotect` and first consumer scan for every method. Report a secondary comparison against the hybrid writing to a pre-touched destination. Reserve and fault that destination before timing for this control. It represents a caller with an already-resident buffer and a different memory contract. Its timing quantifies the sensitivity to first-touch cost.

## Workload and decision

Keep all pilot sizes and layouts, including adjacent and interleaved controls. Use **104729** and **130363** as fresh seeds. Run all five methods once as warm-up and five times for measurement, rotating order by repetition and seed. Pin one thread to logical CPU 4, evict 64 MiB before each trial, and verify every byte of every output after the first timed read. Report eligible bytes, bytes actually mapped and number of mapping calls. Record process peak RSS. Report teardown separately after verification and keep it outside the primary result interval, which ends when the first consumer scan completes.

For each case and seed, report the median across paired repetitions of `fastest fresh reference / candidate`. Treat a ratio of at least 1.3× on both seeds in a non-control layout as a measured synthetic result worth validating on real data. Also report the paired ratio versus the pre-touched reference for every case. Keep negative results and regressions. Practical importance, portability, and novelty relative to prior work require further evidence. If a measured synthetic case reaches 1.5× on both seeds, report it directly to the owner at this checkpoint before broader exploration.

## Reproduction

Use the same [Linux/WSL2 toolchain](../2026-11-12-page-remapped-merge/README.md#reproduction) as the pilot. The [experimental slice materializer](../../prototypes/agents/page-remapped-merge/slice.hpp) is used by the shared harness.

```sh
bash runs/2026-11-12-page-remapped-merge/run.sh lab/page-merge-candidate-smoke --candidate --smoke
bash runs/2026-11-12-page-remapped-merge/run.sh lab/page-merge-candidate --candidate
python3 runs/2026-11-12-page-remapped-merge/analyze.py lab/page-merge-candidate --candidate
```
