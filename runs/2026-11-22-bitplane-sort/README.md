---
title: Stable sorting through bitplane membership masks
date: 2026-11-22 22:09
verdict: failed
summary: Keeping the sort in bit masks took 5.71-6.15 times the direct AVX2 network's time on random byte keys. All 240 timed calls were correct, but neither primary seed approached the speed target.
model: GPT-6 (Codex; exact deployment variant and reasoning settings unavailable)
cost: not captured
idea: 7. Bitplane membership sorting for short stable batches
result: 0.163-0.175x across two primary seeds
baseline: direct batched AVX2 network on 16-bit key and source-position tags
speedup: 0.163-0.175
closes: [scalar prefix traversal of 32-row bitplane membership masks]
how: Turn each bit position of 32 keys into a mask of original row positions. Refine those masks into key order and copy each row to the output once, keeping equal keys in their original order.
compared_with: A direct AVX2 sorting network, pinned Highway and x86-simd-sort libraries, and stable counting sort. Every method includes conversion and output writes, uses one thread and receives ordinary byte keys with four-byte payloads.
faster_where: On the registered random-key batches the candidate took about 225 ns per group and the best reference 37-39 ns. With eight possible keys it still took 77-78 ns versus 36 ns. No registered case beat the direct network.
title_es: Ordenacion estable mediante mascaras de bits
how_es: Se representa cada bit de 32 claves con una mascara de posiciones originales. Se refinan las mascaras hasta obtener el orden y se copia cada registro una sola vez, conservando el orden entre claves iguales.
compared_with_es: Una red AVX2 directa, las bibliotecas Highway y x86-simd-sort y una ordenacion estable por conteo. Todos incluyen conversion y escritura de la salida, usan un hilo y reciben claves de un byte con datos asociados de cuatro bytes.
faster_where_es: En los lotes aleatorios registrados el candidato tardo unos 225 ns por grupo frente a 37-39 ns de la mejor referencia. Con ocho claves posibles siguio tardando 77-78 ns frente a 36 ns. Ningun caso supero a la red directa.
---

# Stable sorting through bitplane membership masks

**Rejected by the preregistered kill test.** Both primary seeds missed the
77%-of-best-time gate by a wide margin. Keep this implementation as a documented
negative result and do not tune its traversal on the measured inputs.
[Protocol registered before implementation](protocol.md)

## What was measured

Each independent group contains 32 uint8 keys and 32 uint32 payloads in separate
ordinary arrays. Inputs are immutable and output uses separate caller-provided
buffers. Sorting is stable. The large cells contain 65,536 groups, or 2,097,152
rows. The candidate pays for extracting all eight membership planes from byte
keys, prefix refinement, enumerating source slots and writing keys and payloads.

The direct reference sorts 16-bit `(key << 5) | source_slot` tags with a fully
batched AVX2 bitonic network, then emits the ordinary output. Highway and
x86-simd-sort use 32-bit tags. The fourth reference performs stable counting
sort with all 256 byte values, including clearing counts and computing offsets.
Importantly, the tag-based references also move payloads only at the end.

Seven measured rounds follow one warm-up per case. Methods are shuffled within
rounds. The table compares medians, with speedup defined as best-reference time
divided by candidate time. [Raw samples](raw.csv) and [all method medians and
sample ranges](analysis.json) are retained.

| Groups | Keys | Seed | AVX2 network, ns/group | Masks, ns/group | Speedup | Paired wins |
|---:|---|---:|---:|---:|---:|---:|
| 65,536 | Uniform byte | 104729 | 36.618 | 225.278 | 0.163x | 0/7 |
| 65,536 | Uniform byte | 130363 | 39.442 | 225.143 | 0.175x | 0/7 |
| 128 | Uniform byte, resident control | 104729 | 47.656 | 169.531 | 0.281x | 0/7 |
| 128 | Uniform byte, resident control | 130363 | 54.688 | 132.812 | 0.412x | 0/7 |
| 65,536 | Eight possible keys | 104729 | 36.198 | 78.314 | 0.462x | 0/7 |
| 65,536 | Eight possible keys | 130363 | 35.860 | 77.367 | 0.464x | 0/7 |

The direct network was the fastest reference in all six cells. On the two
primary cells, Highway took 52.550 and 52.478 ns/group, x86-simd-sort took
48.396 and 52.542 ns/group, and counting took 119.588 and 133.754 ns/group.
The candidate did not win a single paired repetition against the network.
Its primary sample ranges (222.6-232.0 ns/group across both seeds) are disjoint
from the network's ranges (35.2-45.8 ns/group). Timing noise cannot plausibly
turn this result into a pass of the registered gate.

## Interpretation and limits

Membership masks remove intermediate key and record partitioning. They replace
it with scalar prefix traversal and source-slot enumeration. This implementation
does not make that work cheap enough. Fewer possible keys reduce its median
from about 225 to 77-78 ns/group, while the network remains around 36 ns/group.
Traversal and its data-dependent control flow are plausible causes; no branch,
cache or instruction counters were collected, and their individual costs were
not isolated. The resident controls are short calls with visibly more variation.

This was a development kill test, not held-out validation. No fresh-input
performance claim, algorithmic novelty claim, large-array claim or cross-ISA
claim follows. Bit-sliced indexing and SIMD radix sorting are established prior
art; the proposed CPU mask representation was unconfirmed. See the sources and
specific mechanism comparison in the [protocol](protocol.md).

## Verification, hardware and memory

- Verified all 210 measured calls and 30 warm-ups byte for byte on both keys and
  payloads against independent per-group `std::stable_sort`. The correctness
  screen also verified all five methods on 1,024 adversarial groups, including
  all 256 four-position sequences over `{0, 1, 128, 255}` and ties with unique
  source-position payloads. [Verification log](verification.txt)
- AMD Ryzen 7 5800X, Windows 11 build 26200, one thread pinned to logical CPU 8,
  GCC/MinGW-w64 16.1.0. The processor model was read from Windows' hardware
  registry; the direct CIM query was unavailable in the sandbox. [CPU](cpu.json)
- All 65,536-group cells flush input and output cache lines with `CLFLUSH` and
  execute `MFENCE` before starting the timer. Small controls omit the flush.
  Allocation, input generation, flushing, reference construction and verification
  are outside timing for every method. Per-group local scratch is inside it.
- The large harness owns 10 MiB input, 10 MiB output and 10 MiB expected output.
  Methods add small stack buffers: 32 bytes of planes plus traversal state,
  64-byte or 128-byte tags, or 512-byte counts. Compiler spill space and peak
  process residency were not separately sampled.
- Source, runner, protocol and binary hashes, exact reference commits, flags,
  timestamps and command arguments are in [metadata.json](metadata.json).
  No heavy local job was launched concurrently with measurements.

## Reproduction and accounting

[Source and build commands](../../prototypes/agents/bitplane-sort/README.md).
Recompute every median and validate the matrix without benchmarking:

```powershell
python -X utf8 runs/2026-11-22-bitplane-sort/analyze.py `
    runs/2026-11-22-bitplane-sort/raw.csv
```

GPT-6 (Codex). The exact deployment variant, reasoning settings, token usage and
subscription cost were unavailable. External paid compute spend for this screen
was zero. No project goal or status was changed.
