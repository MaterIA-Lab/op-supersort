---
title: Direct span moves after key corrections
date: 2026-11-23 00:47
verdict: promising
summary: Applying a small batch of key corrections to a sorted array ran 1.81–2.10× as fast as the fastest measured reference on fresh 128 and 256 MiB cases. The prototype wrote about half as many unchanged rows. DeltaSort was faster when corrections stayed close to their original ranks.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 9. Move unchanged spans directly after a batch of key corrections
result: 1.810–2.102× across four registered holdout cells and 1.944–2.029× in the supplemental comparison
baseline: fastest median of bulk extract-sort-merge in either direction, upstream DeltaSort and Rust full sorting
speedup: 1.810–2.102
opens: [in-place sorting with unapplied key corrections and original positions]
how: Calculate where each corrected key belongs before writing to the array. Move each affected stretch of unchanged rows directly to its final positions, then place the corrected rows.
compared_with: Two implementations that compact then merge whole stretches, the original DeltaSort, and full sorting with Rust. The additional comparison includes Rust's stable adaptive sorter. Every method receives the original array and unapplied corrections and pays for its temporary allocations.
faster_where: At 128 and 256 MiB, new random keys for about 0.1% of rows gave a speedup of 1.81–2.10× in four fresh cases. DeltaSort took less time in both controls where corrections stayed within about 256 ranks.
title_es: Movimiento directo de tramos tras corregir claves
how_es: Se calcula dónde va cada clave corregida antes de escribir en el array. Se mueven los tramos afectados directamente a su posición final y se colocan los registros corregidos al terminar.
compared_with_es: Dos variantes que compactan y fusionan tramos, la implementación original de DeltaSort y la ordenación completa de Rust. La comprobación adicional incluye la ordenación adaptativa estable de Rust. Todos reciben el array original y las correcciones sin aplicar, y se mide la reserva de memoria auxiliar.
faster_where_es: En arrays de 128 y 256 MiB con claves nuevas aleatorias en cerca del 0,1 % de los registros, aceleró el proceso entre 1,81× y 2,10× con semillas nuevas. DeltaSort fue más rápido en los dos controles de correcciones locales, de hasta unas 256 posiciones.
---

# Direct span moves after key corrections

The prototype exceeded both the 1.3× research target and the 1.5× reporting
threshold in all four preregistered holdout cases. The supplemental comparison
with DriftSort gave 1.94–2.03× on four more inputs. The speed evidence is for
synthetic arrays on one machine. Algorithmic novelty and results on
application traces still need independent validation. The owner was notified
after the development gate and broad exploration was paused.

## Operation and references

The caller starts with a contiguous array in `(key, id)` order and a batch of
unapplied corrections. Each correction gives a new 32-bit key and a unique
original position. The 128-byte records have persistent IDs for ties. Every
method applies the corrections and restores order at the original address.
The old keys stay available until the method begins mutating the array.

The prototype searches the intact original order for the insertion gaps.
Insertions and deletions determine a displacement for each unchanged span.
It moves spans shifting left in source order and spans shifting right in
reverse source order. Each moved unchanged record belongs to one span and
goes straight to its final position. It then fills the remaining positions
with the saved corrected rows. The source directory gives the argument for
safe overlapping copies. [Prototype and build commands](../../prototypes/agents/key-correction-spans/README.md)

The comparisons include the author's unchanged DeltaSort implementation and
two in-place extract-sort-merge (ESM) controls. ESM compacts unchanged rows in
bulk and then merges the sorted corrected rows in bulk in the other direction.
Both ESM controls share the prototype's edit preprocessing and copy primitive.
The original matrix includes Rust's unstable full sort. The supplemental matrix
adds Rust's stable adaptive sort. Timing covers the complete call including
allocating and releasing scratch. [Protocol](protocol.md) · [Supplemental protocol](reference-audit.md)

## Registered holdout results

Each time is the median of seven measured calls after one warm-up. The weight
of the rows and edits is the same for each method in a cell. The ratio is the
fastest reference median divided by the prototype median. Write counts cover
unchanged rows written into the main array, including repeated writes by ESM.

| Array | Edits | Seed | Best reference | Reference, ms | Direct spans, ms | Speedup | Unchanged rows written, spans / reference |
|---|---:|---:|---|---:|---:|---:|---:|
| 128 MiB | 1,024 | 1000003 | Bulk ESM right | 27.532 | 13.570 | 2.029× | 1,025,253 / 2,093,590 |
| 128 MiB | 1,024 | 16777259 | Bulk ESM right | 26.751 | 14.512 | 1.843× | 1,042,182 / 2,093,594 |
| 256 MiB | 2,048 | 1000003 | Bulk ESM left | 62.386 | 29.686 | 2.102× | 2,063,513 / 4,187,811 |
| 256 MiB | 2,048 | 16777259 | Bulk ESM left | 60.653 | 33.501 | 1.810× | 2,082,261 / 4,188,860 |

Direct spans won all 28 measured rounds against the fastest reference chosen
by median in each cell. The candidate made 49.0–49.8% as many writes of unchanged
rows as that reference. Logical writes describe the number of rows the
algorithm asked to copy. Actual cache line and memory bus traffic was not
sampled. [Holdout samples](holdout.csv) · [All holdout medians and ranges](holdout-summary.json)

## Supplemental comparison with DriftSort

The DeltaSort paper uses DriftSort because it detects sorted runs. We added it
on four new fixed inputs with the same candidate source and the same workload
shape. Bulk ESM again had the lowest reference median in every cell. The
prototype won all 28 paired rounds against the fastest reference in each cell.
See [Dwivedi's evaluation](https://drops.dagstuhl.de/storage/00lipics/lipics-vol371-sea2026/html/LIPIcs.SEA.2026.18/LIPIcs.SEA.2026.18.html#S5).

| Array | Seed | Best reference, ms | DriftSort, ms | Direct spans, ms | Speedup |
|---|---:|---:|---:|---:|---:|
| 128 MiB | 1234567 | 27.554 | 184.241 | 14.113 | 1.952× |
| 128 MiB | 98765431 | 25.711 | 155.206 | 13.225 | 1.944× |
| 256 MiB | 1234567 | 57.050 | 378.980 | 28.437 | 2.006× |
| 256 MiB | 98765431 | 54.793 | 364.984 | 27.008 | 2.029× |

[Supplemental samples](reference-audit.csv) · [All supplemental medians and ranges](reference-audit-summary.json)

## Development controls

- With 1,024 uniform replacements at 128 MiB, the two development cells ran
  at 2.042× and 2.097× of the fastest reference by the same timing ratio.
- With just 32 uniform replacements at 128 MiB, the prototype took 8.368 and
  11.809 ms. The best references took 13.684 and 26.771 ms, with DeltaSort
  fastest on the first seed and bulk ESM on the second.
- With 1,024 local corrections at 128 MiB, the prototype took 2.399 and 1.888 ms.
  DeltaSort took 2.263 and 1.643 ms. The prototype took 6–15% longer.
  Close changes shrink the amount to move. The prototype still searches the
  full old key range for each correction.
- The 512 KiB resident controls reached 1.260–1.413× over DeltaSort. One of the
  two seeds passed the 77% time limit.

[Development samples](development.csv) · [All development medians and ranges](development-summary.json)

## Verification, resource use and accounting

- Verified all 588 measured calls and 84 warm-ups using exact equality of
  every key, persistent ID and payload word. Before timing, 1,455 separate
  fixtures tested the five registered methods and checked the minimum possible
  unchanged-row write count. They cover empty and fully edited inputs, repeated
  keys, endpoint insertions and randomly ordered edits. [Verification log](verification.txt)
- AMD Ryzen 7 5800X, Windows 11 build 26200, one thread on logical CPU 8, Rust
  1.96.0 with LLVM 22.1.2 and `target-cpu=znver3`. Restore the working array and
  flush its lines with CLFLUSH and MFENCE outside the large cases' timer. The
  measured array and output share an address. DeltaSort uses commit
  `89322c7bfb8d5b28b179650d08249398cbe0a977`. The development and holdout builds
  have identical executable and source hashes. [Development metadata](development.json) · [Holdout metadata](holdout.json) · [Supplemental metadata](reference-audit.json)
- The prototype requests at most 232 bytes of vector capacity per edit plus
  24 bytes for one more span on this 64-bit build. This is about 232 KiB and
  464 KiB at the two tested counts. Bulk ESM requests 160 bytes per edit.
  Figures come from vector capacities and omit allocator and stack overhead.
  The harness keeps three full arrays for original, working and expected rows
  during timing. Peak residency was not measured.
- Run with `gpt-6.2-sol` in Codex. The exact reasoning setting, token usage and
  subscription cost were not captured. External paid compute spend was zero.

These results support measuring a real workflow that receives correction
positions before overwriting old keys. The original contract and close prior
work are recorded in [idea 9](../../notes/ideas.md#9-move-unchanged-spans-directly-after-a-batch-of-key-corrections).
