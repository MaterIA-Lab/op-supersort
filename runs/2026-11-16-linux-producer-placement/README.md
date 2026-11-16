---
title: Producing two batches and their merged view on Linux
date: 2026-11-16 15:15
verdict: failed
summary: Adjusted page placement was 1.231–1.280× as fast as the best direct writer across eight fresh edge-overlap cases on two Linux runners. Every case missed the 1.30× target, and building the two batches took 80–84% of the remapping time.
model: Codex (exact model and reasoning settings not captured)
cost: not captured
idea: 1. Virtual memory as a data-movement engine
result: 1.231–1.280× on the eight holdout cases, with 0/8 meeting the 77% time limit
baseline: Fastest of split bulk merge and fused cached or streaming writes
speedup: 1.231–1.280
closes: [fresh producer placement using the tested Linux mappings]
how: Choose where each new batch starts so the output can reuse both ends as whole memory pages. Copy the small overlap and expose both batches and the fused result for reading.
compared_with: The fastest direct writer producing the same three readable outputs on one thread, including a first pass over the combined output.
faster_where: With 2% overlap at 128 and 256 MiB, shifting the batches reused about 98% of the bytes. Both shifted versions beat the direct writer in all eight fresh cases, with speedups of 1.231–1.280×. Every case fell short of the 1.30× target.
title_es: Producción de dos lotes y su salida fusionada en Linux
how_es: Se elige dónde empieza cada lote nuevo para reutilizar ambos extremos por páginas de memoria. Se copia la zona de solapamiento y se exponen los dos lotes y la salida fusionada para lectura.
compared_with_es: La escritura directa más rápida que generaba las mismas tres salidas con un hilo, incluida la primera lectura de la salida fusionada.
faster_where_es: Con un 2 % de solapamiento y tamaños de 128 y 256 MiB, ajustar la posición de los lotes permitió reutilizar cerca del 98 % de los bytes. Las dos variantes ganaron en los ocho casos nuevos, con una aceleración de 1,231× a 1,280×. Los ocho casos quedaron por debajo del objetivo de 1,30×.
---

# Producing both batches and their merged view on Linux

On two Linux virtual machines, choosing each batch's starting position reused about 98% of output bytes. The lazy and eager mapping variants each beat the direct reference in all 40 paired holdout repetitions. Each cleared the registered 77% time limit in zero of eight holdout cells. The fused writer with cached stores had the fastest direct median in all 24 runner and input combinations. [Registered protocol](protocol.md)

## Holdout results

The inputs were two sorted buffers of synthetic 128-byte records with about 2% overlap in key range. The timed call produced two new read-only batches and their contiguous stable merged view, then read one word from each cache line of that view. The original buffers were resident, with their cache lines flushed before timing. Medians use five repetitions per case. Speedups divide the best direct median by the corresponding mapping median.

| Runner | Merged size | Seed | Direct, ms | Fixed, ms | Shifted lazy, ms | Shifted eager, ms | Lazy speedup | Eager speedup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 128 MiB | 1907348639 | 115.954 | 126.112 | 91.124 | 90.556 | 1.272× | 1.280× |
| 1 | 128 MiB | 185028962 | 114.428 | 126.023 | 89.461 | 89.475 | 1.279× | 1.279× |
| 1 | 256 MiB | 1907348639 | 232.002 | 258.272 | 183.340 | 184.279 | 1.265× | 1.259× |
| 1 | 256 MiB | 185028962 | 235.067 | 259.958 | 184.519 | 185.591 | 1.274× | 1.267× |
| 2 | 128 MiB | 1907348639 | 91.658 | 100.702 | 72.684 | 72.023 | 1.261× | 1.273× |
| 2 | 128 MiB | 185028962 | 91.419 | 101.942 | 72.771 | 71.618 | 1.256× | 1.276× |
| 2 | 256 MiB | 1907348639 | 188.538 | 207.652 | 153.167 | 152.689 | 1.231× | 1.235× |
| 2 | 256 MiB | 185028962 | 186.915 | 208.568 | 149.167 | 146.986 | 1.253× | 1.272× |

Fixed alignment reused 48.998–49.001% of the output and ran at 0.896–0.919× of the direct writer's speed. Both shifted variants reused 97.996–97.999%. Building the memory-backed input batches took 80–84% of their end-to-end time. Populating the read-only aliases during assembly increased the median assembly time by 2.650–8.710 ms and shortened the first read by 3.565–8.317 ms. The change in the total median ranged from a 2.181 ms saving to a 1.072 ms cost. Phase medians and the total median are computed independently.

Adding the separately timed teardown after verification, the per-cell median of total plus teardown was 81.1–85.1% of the direct time for lazy mapping and 81.7–84.5% for eager mapping, compared with the same direct writer. The mapping used roughly 131 or 261 MiB of distinct output payload backing at the two sizes plus page padding. Direct writing used about 256 or 512 MiB. These figures follow from the mapped-byte counts and describe the three output buffers. The original buffers and verifier use additional memory.

## Controls and scope

- The earlier two seeds at both sizes gave 1.238–1.295× for lazy placement and 1.252–1.288× for eager placement across the two runners.
- The four disjoint controls reused more than 99.99% of output bytes. They reached 1.259–1.300× with lazy mapping and 1.271–1.308× with eager mapping. One lazy median and two eager medians met the 77% time limit. These controls used disjoint synthetic ranges at 128 MiB.
- The four interleaved controls reused zero pages. Both shifted methods took 1.31–1.36 times the direct writer's time.

This closes the tested Linux implementation for producing the three fresh outputs on this workload. The direct and mapped timings start with sorted working buffers. The Windows test used the same three-output contract on different hardware. The earlier Linux merge started with prepared inputs. [Windows producer benchmark](../2026-11-16-producer-page-placement/README.md) · [Earlier Linux merge](../2026-11-12-page-remapped-merge-candidate/summary.md)

## Verification and reproduction

All 720 timed samples, 144 warm-ups and the smoke checks in both corrected jobs passed bytewise verification of all three outputs against the original batches and a stable reference merge. Both jobs used one thread pinned to vCPU 3, 4 KiB pages, GCC 13.3 and glibc 2.39 on Ubuntu 24.04. Runner 1 used a Xeon Platinum 8573C VM and runner 2 used a Xeon 6975P-C VM. The final measurement used `CLFLUSHOPT` on both. The initial 96 MiB sweep was insufficient to establish cold inputs given the reported 480 MiB L3 on the first runner. The full matrix was rerun with explicit source flushing. The two initial jobs are retained for audit. The benchmark source and flags are pinned by the [corrected workflow](https://github.com/MaterIA-Lab/op-supersort/actions/runs/43893770752). [Initial workflow](https://github.com/MaterIA-Lab/op-supersort/actions/runs/43892454332)

| Configuration | Runner 1 | Runner 2 |
|---|---|---|
| Input lines explicitly flushed | [CSV](runner-1.csv) · [metadata](runner-1-metadata.txt) | [CSV](runner-2.csv) · [metadata](runner-2-metadata.txt) |
| Initial 96 MiB sweep | [CSV](initial-runner-1.csv) · [metadata](initial-runner-1-metadata.txt) | [CSV](initial-runner-2.csv) · [metadata](initial-runner-2-metadata.txt) |

From the repository root, regenerate the result from the corrected raw samples.

```sh
python -X utf8 runs/2026-11-16-linux-producer-placement/analyze.py \
  runs/2026-11-16-linux-producer-placement/runner-1.csv \
  runs/2026-11-16-linux-producer-placement/runner-2.csv
```

For a new measurement, use the [build and run commands](../../prototypes/agents/producer-page-placement/README.md) on Linux or the benchmark workflow. This iteration used four standard GitHub-hosted benchmark jobs. Token counts and marginal provider costs were unavailable.
