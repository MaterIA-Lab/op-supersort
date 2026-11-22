---
title: Sparse saved-row cuts for in-place record permutation
date: 2026-11-22 22:26
verdict: failed
summary: Interleaved paths reduced the full sort from 126-129 ms with ordinary cycles to 52-53 ms, but streaming gather plus copy-back still won at 48-49 ms. Both primary inputs missed the speed target.
model: GPT-6 (Codex; exact deployment variant and reasoning settings unavailable)
cost: not captured
idea: 8. Sparse saved-row cuts for interleaved in-place permutation
result: 0.908-0.931x across two primary seeds
baseline: vqsort tags plus prefetched non-temporal gather and streaming copy-back
speedup: 0.908-0.931
closes: [64 saved-row cycle cuts under the registered reusable-workspace contract]
how: Save a few original rows so long chains of record moves can be split into independent paths. Interleave the paths on one thread, reading ahead in memory, and finish the untouched cycles afterward.
compared_with: Compact SIMD key sorting followed by ordinary cycles or gather-and-copy-back, plus direct pdqsort on records. Every method returns the result at the original address and may use the same reusable workspace.
faster_where: For 128 MiB of 128-byte records with random keys, the candidate took 52.3-53.0 ms versus 48.1-48.7 ms for the best reference, a 7-10% regression. It was 2.38-2.47x faster than ordinary cycles. Neither primary seed passed the gate.
title_es: Cortes con registros guardados para permutar datos en su mismo espacio
how_es: Se guardan unos pocos registros originales para dividir cadenas largas de movimientos en tramos independientes. Se intercalan esos tramos con un hilo, adelantando lecturas de memoria, y se terminan aparte los ciclos restantes.
compared_with_es: Ordenacion SIMD de claves compactas seguida de ciclos o de copia a un buffer y vuelta, ademas de pdqsort directo sobre registros. Todos devuelven la salida en la direccion original y pueden usar el mismo espacio auxiliar reutilizable.
faster_where_es: Con 128 MiB de registros de 128 bytes y claves aleatorias, el candidato tardo 52,3-53,0 ms frente a 48,1-48,7 ms de la mejor referencia, un 7-10 % mas. Supero los ciclos ordinarios por 2,38-2,47x. Ninguna semilla principal paso el criterio.
---

# Sparse saved-row cuts for in-place record permutation

**Rejected by the registered kill test.** The implementation substantially
improves on ordinary cycle rotation but misses the target against the stronger
gather-and-copy-back reference. Checkpoint count was fixed at 64 before timing
and was not tuned after these results. No held-out performance claim follows.
[Preregistered protocol](protocol.md)

## Mechanism and contract

Sort `(uint32 key, uint32 source_position)` tags with pinned Highway vqsort.
Before moving any record, save up to 64 rows at power-of-two-stride positions.
Each starts a permutation walk which stops at any saved position and uses its
backup instead of reading overwritten data. Interleave these disjoint paths,
prefetch both cache lines of each next source row, and mark completed tags.
Finish all cycles containing no checkpoint with ordinary cycle rotation.
[Safety argument, implementation and build commands](../../prototypes/agents/checkpoint-cycles/README.md)

All routines sort the same mutable 128-byte records, return at the original
base address and preserve the input order of equal keys. They receive reusable
caller-owned scratch for N tags and N records. The candidate uses the tags and
small saved-row state; gather references also use the full record buffer.
Workspace allocation and first touch are outside timing for every method.
Tag extraction, sorting, all mark writes, fallback scanning, record movement,
copy-back where applicable, and non-temporal-store fences are inside timing.

Each record contains a 32-bit key, a unique 32-bit input ordinal and fifteen
64-bit payload words. Comparing `(key, ordinal)` gives the common stable order.
The direct record reference uses the unmodified archived pdqsort header.

## Measurements

Medians of five measured rounds following one warm-up. Methods are shuffled
within each round. Speedup is fastest-reference median divided by candidate
median; values below one mean slower. [Raw CSV](raw.csv) and [all method medians
and sample ranges](analysis.json).

| Records | Keys | Seed | Best reference | Reference, ms | Checkpoints, ms | Speedup | Paired wins |
|---:|---|---:|---|---:|---:|---:|---:|
| 1,048,576 | Uniform32 | 48071 | vqsort + streaming gather and copy-back | 48.150 | 53.004 | 0.908x | 1/5 |
| 1,048,576 | Uniform32 | 65827 | vqsort + streaming gather and copy-back | 48.696 | 52.286 | 0.931x | 1/5 |
| 8,192 | Uniform32, resident control | 48071 | vqsort + ordinary cycles | 0.247 | 0.222 | 1.115x | 3/5 |
| 8,192 | Uniform32, resident control | 65827 | vqsort + ordinary cycles | 0.186 | 0.201 | 0.924x | 1/5 |
| 1,048,576 | Eight possible keys | 48071 | vqsort + streaming gather and copy-back | 45.845 | 49.206 | 0.932x | 1/5 |
| 1,048,576 | Eight possible keys | 65827 | vqsort + streaming gather and copy-back | 46.911 | 52.721 | 0.890x | 0/5 |

Neither primary cell passed the requirement that candidate time be at most 77%
of the best reference. Both primary timings are development inputs. The one
small-control win is not a finding and does not change the registered class.

### What the controls show

| Uniform32 seed | Ordinary cycles, total ms | Checkpoints, total ms | Cached gather and memcpy back, total ms | Streaming gather and copy-back, total ms | Direct pdqsort, total ms |
|---:|---:|---:|---:|---:|---:|
| 48071 | 126.259 | 53.004 | 55.602 | 48.150 | 100.570 |
| 65827 | 129.151 | 52.286 | 52.082 | 48.696 | 100.474 |

For these seeds the separately computed phase medians were:

- Checkpoints: 16.600/17.329 ms to extract and sort tags, then 36.099/34.957 ms
  to complete the in-place permutation.
- Ordinary cycles: 17.660/16.908 ms to extract and sort tags, then
  106.858/112.243 ms to move records.
- Streaming gather with Highway: 17.350/17.100 ms for tags and
  31.111/31.906 ms for gather plus copy-back and fences.
- x86-simd-sort with the same streaming materialization: 51.567/51.004 ms total.

Phase medians are independent and do not necessarily sum to the total median.
The method-specific index phase for direct pdqsort contains its whole operation;
it has no separately timed materialization phase.

The saved-row cuts and interleaving remove much of ordinary cycle rotation's
cost: 2.38-2.47x total and roughly 2.96-3.21x in materialization relative to that
reference. They do not beat streaming gather even though the latter copies the
payload twice. Fewer logical payload transfers are insufficient here. Random
tag and row access, the shrinking set of active paths and untouched serial
cycles are possible remaining costs, but this run did not isolate them or
collect hardware counters. Small controls show visible timing variation.

## Memory and limits

At N=1,048,576 the candidate's algorithmic auxiliary storage is an 8 MiB tag
array, at most 8 KiB of saved rows, two 64-entry uint32 cursor arrays and a
scalar fallback row, apart from compiler spill space. The streaming gather
method additionally needs 128 MiB of record scratch. These are storage
requirements inferred from the source, not separately measured peak residency.
The harness keeps the full caller-owned scratch alive for every method; it
therefore does not measure a process-memory reduction when the candidate runs.

Do not reinterpret these inputs under a new memory ceiling to manufacture a
win. The registered contract allowed reusable full-record scratch. A separate
practical memory-constrained question would need its own declared workload,
fresh inputs and strongest references. Likewise the implementation was not
validated with fresh per-call allocation, on another ISA or on application data.

Cycle-leader permutation, cache-aware cycle scheduling and block movement are
prior art. The specific proposed difference is a sparse saved-row cut that
creates safe independent streams without a prior cycle-discovery traversal.
Novelty has not been established. IPS4o and the record-oriented SIMD merge
remain missing strong comparisons for any future positive claim. A failure
against the measured streaming reference already suffices to kill this version
under the declared contract.

## Verification and reproduction

- All 180 measured calls and 36 warm-ups matched the independent oracle byte
  for byte on every complete row. The oracle is a `std::sort` of original
  ordinals by the original `(key, ordinal)` values.
- Before timing, all four permutation movers passed 46,410 supplied
  permutations, including every permutation through length eight. Tests also
  cover arbitrary lengths through 4,097, identity, reversal, a single long
  cycle, isolated three-cycles without checkpoints and randomized cycles.
  All six full sort methods passed 66 additional checks with duplicate keys.
  [Verification log](verification.txt)
- AMD Ryzen 7 5800X, Windows 11 build 26200, one thread on logical CPU 8,
  GCC/MinGW-w64 16.1.0 with `-O3 -march=znver3 -mavx2 -DNDEBUG -std=c++20`.
  No heavy local workload was launched concurrently with these measurements.
  [CPU record](cpu.json)
- Before large calls, reset the working rows, CLFLUSH every working row and
  both scratch arrays, then MFENCE outside timing. Resident controls omit the
  flush. The large harness owns three 128 MiB row arrays (original, working,
  reusable scratch), 8 MiB tags and 4 MiB oracle ordinals, about 396 MiB of
  payload and index allocations before runtime overhead. Small cases use the
  analogous 3.094 MiB. No peak residency or TLB counters were sampled.
- Both vendor repositories were clean at their pinned commits. Source, runner,
  protocol, binary and pdqsort-header hashes, exact flags and timestamps are
  preserved in [metadata.json](metadata.json).

Recompute and validate the complete matrix without rerunning benchmarks:

```powershell
python -X utf8 runs/2026-11-22-checkpoint-cycles/analyze.py `
    runs/2026-11-22-checkpoint-cycles/raw.csv
```

## Accounting

GPT-6 (Codex). Exact deployment variant, reasoning settings, token usage and
session cost were unavailable. External compute spend for this local screen
was zero. The research goal and project status were not changed.
