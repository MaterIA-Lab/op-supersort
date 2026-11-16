---
title: Helper-thread prefetch for scattered records
date: 2026-11-15 15:26
verdict: failed
summary: The best helper took 180–182 ms on two threads of one core. Giving each thread half the output took 102–114 ms for the same 256 MiB permutation.
model: Codex (exact model and reasoning settings not captured)
cost: not captured
idea: 6. Helper threads for memory-level parallelism
result: 0.564–0.629× against the fastest split gather
baseline: fastest of seven split gathers on the same two hardware threads
speedup: 0.564–0.629
closes: [128-byte random gather with a bounded prefetch helper]
how: One thread copies all the records. A second thread looks ahead in the destination order and asks the CPU to bring the next records into cache.
compared_with: Seven methods using the same two hardware threads to copy one half each, including in-thread prefetch and stores that bypass cache.
faster_where: On the two 256 MiB permutations with threads sharing one core, the best helper took 59–77% longer than the fastest split. It did beat the single-worker control by 1.16–1.46×. The benchmark measures copying in the supplied order.
title_es: Hilo auxiliar para precargar registros dispersos
how_es: Un hilo copia todos los registros. El segundo lee por adelantado el orden de salida y solicita al procesador que cargue los próximos registros en caché.
compared_with_es: Se probaron siete formas de copiar una mitad con cada hilo en los mismos dos hilos de hardware, con precarga en el propio hilo y opciones de escritura directa a memoria.
faster_where_es: Para las dos permutaciones de 256 MiB con hilos que comparten núcleo, la mejor variante con precarga auxiliar tardó un 59–77 % más que la copia repartida. Frente a un único hilo copiando, fue entre 1,16× y 1,46× más rápida. La prueba mide la copia en un orden dado.
---

# Helper-thread prefetch for scattered records

On both primary seeds, using both hardware threads to write the output beat every measured arrangement with a dedicated helper. Demand-loading the first byte of both source cache lines with a 1,024-row limit was the fastest helper on both seeds. It beat the one-writer reference in these large cases. The direct split had enough additional throughput to win under an equal hardware-thread budget. [Preregistered protocol](protocol.md) · [Raw samples](raw.csv) · [Analyzer](analyze.py) · [Environment and hashes](metadata.txt)

| Placement | Records | Seed | Fastest split (ms) | One worker (ms) | Fastest helper (ms) | Split ÷ helper | Requests by best helper | Paired wins for helper |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SMT siblings | 32,768 | 104729 | 4.250 | 5.568 | 5.950 | 0.714× | 54.3% | 3/7 |
| SMT siblings | 32,768 | 130363 | 1.332 | 2.038 | 2.429 | 0.548× | 48.4% | 3/7 |
| SMT siblings | 2,097,152 | 104729 | 101.611 | 209.159 | 180.215 | 0.564× | 56.7% | 0/7 |
| SMT siblings | 2,097,152 | 130363 | 114.146 | 265.090 | 181.594 | 0.629× | 55.2% | 2/7 |
| Separate cores | 2,097,152 | 104729 | 90.746 | 205.346 | 128.533 | 0.706× | 76.9% | 2/7 |
| Separate cores | 2,097,152 | 130363 | 76.252 | 223.578 | 141.805 | 0.538× | 78.8% | 0/7 |

The table uses medians from seven measured trials, excluding one warm-up. The paired counts compare the two methods named by their fastest median in each case. All four large cases favored a split with non-temporal stores. Restricting both sides to cached stores still gives 120.752 ms versus 180.215 ms and 145.438 ms versus 181.594 ms on the primary seeds. The helper requested both cache lines of 55–57% of rows on the primary seeds, measured by its issued operations. Cache hit rates and the cause of missed lookahead were not instrumented.

The small control had wide time variation and includes barrier wake-up and scheduling. The gate uses the larger cases only. The timing includes synchronizing both persistent threads and fencing streaming stores. It covers one supplied permutation into a resident allocation. Sorting the keys, building the permutation and any later consumer work are outside this microbenchmark.

Verified 546 measured outputs and 78 warm-up outputs byte for byte, plus 52 smoke outputs. No helper variant reached 1.30× on either primary seed. Close this bounded helper design for the declared gather workload. [Source and build instructions](../../prototypes/agents/smt-gather-helper/README.md)
