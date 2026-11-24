---
title: Placing records directly at their merge ranks
date: 2026-11-24 15:58
verdict: failed
summary: Comparing keys in short groups and placing records at their final ranks missed the 1.30× target in both timing runs. Replaying the same copies with the positions already known reached at most 1.280×.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 12. Write records directly to short-window merge ranks
result: 0.738-1.037× across the original and repeated primary comparisons
baseline: Fastest verified median of direct branching, branchless, bulk-span and bitonic SIMD key/index merges with the tested store variants
closes: [eight-key rank windows for cold stable merges of 64-byte records]
speedup: 0.738-1.037
how: Compare short groups from two sorted batches to find the final slots of the next records. Copy each record once, visiting all records from one batch in that group before the other.
compared_with: Merges that choose the next row one at a time, copy consecutive runs in bulk, or use the CPU's vector instructions to merge several keys at once. The fastest references wrote straight to the output without bringing its old cache lines into cache.
faster_where: On 16 and 64 MiB of randomly interleaved 64-byte records, the fastest version ran 0.738-1.037 times as fast as the best reference across both timing runs. The one small apparent gain disappeared when repeated.
title_es: Copiar los registros directamente a su posición final al fusionar
how_es: Se comparan grupos pequeños de claves de dos lotes ordenados para calcular las próximas posiciones de salida. Cada registro se copia una vez, primero los de un lote y después los del otro dentro de cada grupo.
compared_with_es: Fusiones que eligen una fila cada vez, copian tramos completos o usan instrucciones vectoriales de la CPU para fusionar varias claves a la vez. Las referencias más rápidas escribían en la salida sin cargar en caché su contenido anterior.
faster_where_es: Con 16 y 64 MiB de registros de 64 bytes intercalados al azar, la variante más rápida rindió entre 0,738× y 1,037× frente a la mejor referencia en las dos rondas de medición. La pequeña ventaja de un caso desapareció al repetirlo.
---

# Placing records directly at their merge ranks

**Decision. Close eight-key rank windows for this merge.** They missed
the 77% time gate in every primary case. A repeat with the same input
and build settings confirmed the decision. The holdout was conditional
on the first screen passing. [Protocol](protocol.md) · [Repeatability check](repeatability.md) · [Prototype](../../prototypes/agents/rank-window-merge/README.md)

## Timing

The two input batches are already sorted and have separate dense key
columns. A stable merge materializes all 64-byte records in a reused
output buffer. The benchmark flushes input and output from cache and
times all rank calculations, record copies and the final store fence.
Each number is a median of seven measured calls after two warm-ups.
The best reference is selected from six eligible methods per input.

| Run | Input | Seed | Best reference | Reference, ms | Rank windows, ms | Replay, ms | Ref. / rank |
|---|---|---:|---|---:|---:|---:|---:|
| First | 16 MiB uniform | 25771 | SIMD tags, streaming | 1.686 | 2.033 | 1.750 | 0.830× |
| First | 16 MiB uniform | 63487 | Branchless, streaming | 1.892 | 1.826 | 1.478 | 1.037× |
| First | 64 MiB uniform | 25771 | Branchless, streaming | 6.413 | 6.761 | 6.523 | 0.949× |
| First | 64 MiB uniform | 63487 | Branchless, streaming | 6.680 | 7.175 | 5.866 | 0.931× |
| Repeat | 16 MiB uniform | 25771 | Branchless, streaming | 1.517 | 2.057 | 1.367 | 0.738× |
| Repeat | 16 MiB uniform | 63487 | Branchless, streaming | 1.540 | 1.738 | 1.430 | 0.886× |
| Repeat | 64 MiB uniform | 25771 | Branchless, streaming | 6.681 | 6.695 | 6.418 | 0.998× |
| Repeat | 64 MiB uniform | 63487 | Branchless, streaming | 6.533 | 6.698 | 8.639 | 0.975× |

The table shows rank windows and replay with streaming stores. They
had lower medians than their respective cached-store variants in
every primary cell. The branchless streaming reference won seven of
the eight primary evaluations. Disassembly confirmed the key-based
source selection in that loop emitted a conditional move.
[First-run samples](development.csv) · [Repeat samples](repeat/development.csv)

The uniform workloads switched sources on about 50% of adjacent
records. The 16 MiB alternating-range control switched on 1.56%.
On those four control evaluations, the rank-window method reached
0.898-1.075×. The 1.075× result from the first run became 0.976×
for the same input in the repeat.

## What the replay shows

Replay reads a list of window masks computed before timing and uses
the same source-ordered copies. It still pays to read that list and
to write the result. The best replay reached 0.756-1.280× on uniform
keys across the two runs, with zero medians at the 1.30× gate.
Single-call times varied, and the largest replay advantage appeared
once. The direct reference already writes each record once, with
software-selected streaming stores. This diagnostic gives little
reason to invest in rank calculation alone for the tested merge.

## Verification and accounting

- Both runs verified every returned key, source ID and payload byte
  against a stable `std::merge`. The output was filled with zeros
  before each call. Across the two runs, 840 measured calls and 240
  warm-ups passed. Each build also verified 864 fixtures across all
  ten methods, including empty input and unsigned tie boundaries.
  [First preflight](verification.txt) · [Repeat preflight](repeat/verification.txt)
- One thread pinned to logical CPU 8 on an AMD Ryzen 7 5800X with
  Windows 11, MinGW GCC 16.1.0 and `-O3 -march=znver3`. These are
  synthetic inputs with already available key columns and cold
  buffers. [First build](development-metadata.json) · [Repeat build](repeat/development-metadata.json)
- The input columns take 1 or 4 MiB and the shared output takes
  16 or 64 MiB. Competitive methods use constant-size local
  state and request no dynamic scratch. The SIMD control holds four
  carry tags and up to four output tags. The rank method holds one
  window mask. Replay consumes 81,480-326,204 bytes of masks on
  uniform keys. The harness also reserves the independent oracle
  and its input buffers. Peak process memory was not measured.
- Model `gpt-6.2-sol`. External paid compute spend was zero.
  Model tokens, reasoning setting and session cost were not captured.

Regenerate all ten medians and validate the file digests and sample
schedule from the repository root.

```powershell
python -X utf8 runs/2026-11-24-rank-window-merge/analyze.py development
python -X utf8 runs/2026-11-24-rank-window-merge/analyze.py development --work runs/2026-11-24-rank-window-merge/repeat
```
