---
title: Placing both batches for page reuse during a stable merge
date: 2026-11-16 13:34
verdict: failed
summary: With 2% overlap, independent placement doubled reusable coverage from 49% to about 98%. The Windows implementation took 1.84–2.43 times as long as the best direct reference when producing both batches and the merged result.
model: Codex (exact model and reasoning settings not captured)
cost: not captured
idea: 1. Virtual memory as a data-movement engine
result: 0.412–0.543× against the fastest direct method
baseline: Fastest of split bulk merge and fused cached or streaming writers
speedup: 0.412–0.543
closes: [producer-side page placement with this Windows mapping path]
how: Two searches find the ends that stay together when merging. The producer chooses where the batches start so the program can reuse both ends as whole pages and copy the middle.
compared_with: Compared with fixed alignment and with the fastest direct method that produced both separate batches and a contiguous merged output.
faster_where: At 128 and 256 MiB with 2% overlap, the new placement reused about 98% of the bytes and sped up fixed remapping by 1.10–1.36×. It took 1.84–2.43 times as long as the best direct writer. Batch construction and first read dominated.
title_es: Alineación de los lotes para reutilizar páginas en una mezcla estable
how_es: Dos búsquedas encuentran los extremos que siguen juntos en la salida. Se elige dónde empieza cada lote para reutilizar ambos extremos por páginas y copiar el centro.
compared_with_es: Se comparó con la alineación fija y con la forma directa más rápida de producir los dos lotes y una salida fusionada contigua.
faster_where_es: Con 128 y 256 MiB y un 2 % de solapamiento, se reutilizó cerca del 98 % de los bytes. La aceleración frente al remapeo fijo fue de 1,10× a 1,36×. El método tardó entre 1,84 y 2,43 veces lo que tardó la mejor escritura directa. La preparación y la primera lectura concentraron el coste.
---

# Placing input batches for page reuse during a stable merge

Independent input placement reused about 98% of the primary output bytes, up from about 49% with fixed alignment. The Windows implementation cleared the speed threshold in zero of four primary cases. It lost all 20 paired primary comparisons against the direct method with the quickest median in that cell. See the [registered protocol](protocol.md), [raw samples](raw.csv), [analyzer](analyze.py), and [hardware and build record](metadata.txt).

| Output | Seed | Fastest direct method | Direct, ms | Fixed remap, ms | Shifted remap, ms | Fixed coverage | Shifted coverage | Direct time ÷ shifted time |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 128 MiB | 4316079 | Fused streaming | 139.85 | 305.62 | 276.72 | 49.00% | 97.99% | 0.505× |
| 128 MiB | 99237281 | Split bulk merge | 174.20 | 436.57 | 320.92 | 49.00% | 97.99% | 0.543× |
| 256 MiB | 4316079 | Fused streaming | 218.67 | 664.68 | 530.74 | 49.00% | 98.00% | 0.412× |
| 256 MiB | 99237281 | Fused streaming | 233.47 | 627.30 | 540.02 | 49.00% | 98.00% | 0.432× |

The primary pairs were synthetic 128-byte records with 2.00% of rows inside the shared key range. As specified, the run returns two new contiguous read-only batches and a contiguous read-only merged view. All outputs use one lifetime. The producer's sorted working buffers are resident at the start. Times are medians of five measured rounds per cell.

## Where the time went

| Output | Seed | Shifted batch construction, ms | Shifted assembly, ms | Shifted first read, ms | Direct first read, ms |
|---|---:|---:|---:|---:|---:|
| 128 MiB | 4316079 | 151.88 | 12.46 | 106.56 | 14.12 |
| 128 MiB | 99237281 | 174.38 | 14.51 | 135.92 | 23.72 |
| 256 MiB | 4316079 | 301.73 | 24.84 | 203.78 | 28.81 |
| 256 MiB | 99237281 | 307.90 | 23.26 | 210.84 | 27.08 |

Choosing the offsets made output assembly substantially cheaper than fixed remapping. The shifted method sped up that reference by 1.10–1.36× in the four primary medians. Constructing its pagefile-backed inputs alone already exceeded the entire time budget for a 1.30× win against the direct method in every case. The first scan alone exceeded that budget in three of four cases. These timings include the first access through the assembled address range. No page-fault counters were sampled. Separate phase medians can sum to a different value from the median total.

In the disjoint controls, the shifted layout reused more than 99.99% of bytes and took 2.24–2.64 times as long as the direct reference. The fully interleaved controls reused zero pages and took 2.76–2.84 times as long. Teardown after bytewise verification adds further time in the raw samples. Time variability limits conclusions about which direct method is generally fastest, especially in the controls.

All 200 timed calls, 40 warm-ups and 105 small checks matched the original separate batches and an independent stable merge byte for byte. The generator correction and full rerun are documented in the protocol. The result closes this Windows mapping path for this fresh-output contract. The same producer contract remains unmeasured on Linux, where earlier experiments started with already prepared inputs.

[Exact Windows source and build commands at the recorded revision](https://github.com/MaterIA-Lab/op-supersort/tree/b5338a11c2d3af010b2bf4479f7a12396441b64c/prototypes/agents/producer-page-placement)
