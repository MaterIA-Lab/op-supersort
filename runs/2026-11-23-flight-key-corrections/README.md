---
title: Flight departure time corrections
date: 2026-11-23 01:11
verdict: failed
summary: The direct-span prototype took 29-31% longer than the fastest reference in the median day of a 28-day replay. The sample contained 32,735 flights. DeltaSort was the fastest reference in 50 of 56 day and cache combinations.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 9. Move unchanged spans directly after a batch of key corrections
result: 0.761-0.775× median speedup, with 0/28 days passing in either cache regime
baseline: fastest median among DeltaSort, two full-array and two interval-limited extract-sort-merge variants, and two Rust full sorts
closes: [direct span moves for the tested 4 MiB flight replay]
speedup: 0.761-0.775
how: Start with 32,735 flights ordered by departure time. For 28 days, replay the replacement of scheduled times with reported departure times in daily batches. Use the same prototype that moves each affected stretch directly to its final position.
compared_with: Original DeltaSort, stable and unstable sorting in Rust, and four variants of compacting and merging. Two of the merge variants only process the range touched by the corrections. All methods include temporary memory allocation.
faster_where: The prototype took 29-31% longer in the median day, measured with and without flushing the array from cache. No day reached the target in either regime. The median corrected record moved only one position across the daily medians.
title_es: Corrección de horarios de salida de vuelos
how_es: Se parte de 32.735 vuelos ordenados por hora de salida. Durante 28 días se sustituyen las horas previstas por las reales en lotes diarios. Se usa el mismo prototipo que mueve cada tramo afectado directamente a su posición final.
compared_with_es: DeltaSort original, la ordenación estable e inestable de Rust y cuatro variantes de compactación y fusión. Dos solo procesan el intervalo afectado por las correcciones. La medición incluye la reserva de memoria auxiliar en todos los métodos.
faster_where_es: El prototipo tardó un 29-31 % más que la mejor referencia en la mediana de los días, según el estado de la caché. Ningún día alcanzó el objetivo. En un día típico, el desplazamiento mediano fue de una posición.
---

# Flight departure time corrections

The frozen prototype missed its registered gate in both cache regimes. The
original DeltaSort was the fastest reference in 25 of 28 days in each regime.
Six other cases went to the interval-limited merge controls. The previous
1.81-2.10× result measured random replacements across much larger arrays.
[Preregistered protocol](protocol.md) · [Previous experiment](../2026-11-23-key-correction-spans/README.md)

## Results

The speed ratio is the fastest reference median divided by the direct-span
median for a day and cache regime. The gate required a candidate median at
most 77% of the fastest reference time on 21 of 28 days in each regime.

| Array before timing | Median speed ratio | Day-level range | Days faster | Days passing the gate | Fastest references |
|---|---:|---:|---:|---:|---|
| Reset and flushed | 0.775× | 0.448-1.025× | 1/28 | 0/28 | DeltaSort 25, regional ESM right 2, regional ESM left 1 |
| Reset by copy | 0.761× | 0.614-0.986× | 0/28 | 0/28 | DeltaSort 25, regional ESM left 3 |

On July 1, for example, 86 edits touched a 93-row interval of the 32,735-row
array. After flushing, the median was 7.8 µs for direct spans, 6.5 µs for
DeltaSort and 9.4 µs for the faster regional ESM. After a copy reset it was
9.5, 6.6 and 7.2 µs respectively. Direct spans moved seven unchanged rows.
Each regional ESM moved 14. The full-array ESM variants requested more than
32,000 unchanged-row writes in this case. Limiting the merge to the affected
interval makes it competitive. Using only the two regional ESM variants as
references gives a median direct-span speed ratio of 0.854× in flushed cases
and 0.836× in copy-reset cases. [All day medians and counts](summary.json)

| Daily input property | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Corrections | 63 | 85.5 | 108 |
| Rows in affected interval | 65 | 91.5 | 172 |
| Corrected row rank displacement, daily p50 | 0 | 1 | 3 |
| Corrected row rank displacement, daily p95 | 2 | 5 | 10 |
| Largest corrected-row displacement | 5 | 12.5 | 84 |
| Minimum unchanged-row writes | 0 | 4 | 76 |

Direct spans matched the minimum unchanged-row write count in every case.
There were only four such writes in the median day, so the absolute amount
of movement available to save was small. Two regional merges already confined
their copies to intervals covering a median of 92 rows. The prototype still
searched the full original order for each replacement. The experiment did
not time search and copying separately. [Input geometry](geometry.csv)

## Method, verification and costs

- The replay uses the pinned public OpenIntro sample with all 32,735 flights.
  Departure clocks and delays come from the source. Daily batching and row
  payloads are modeled. The caller supplies the original positions, so the
  measurement excludes snapshot creation and application-level lookup.
  Each output stays at the same address. Each method pays for planning,
  sorting, row copies and scratch allocation and deallocation.
- Run on a single thread pinned to logical CPU 8 of an AMD Ryzen 7 5800X,
  with Windows 11 build 26200 and Rust 1.96.0 targeting `znver3`. The array
  occupies 4,190,080 bytes. Apply CLFLUSH and MFENCE to its address range for
  flushed calls. The timing loop permutes method order and cache regime order.
  DeltaSort is pinned at `89322c7bfb8d5b28b179650d08249398cbe0a977`.
  [Source and machine metadata](metadata.json)
- Verified 3,136 measured calls and 448 warm-ups against a snapshot sorted
  independently by key and persistent ID. Every payload word was compared.
  Verified the exact minimum logical unchanged-row writes for direct spans and
  a lower bound on the counted merge writes. No physical memory traffic was
  sampled. [January](jan.csv) · [April](apr.csv) · [July](jul.csv) · [October](oct.csv)
- At the largest batch of 108 edits, vector capacities request up to 25,080
  bytes for direct spans and 19,008 bytes for regional ESM on this build.
  This excludes allocator and stack overhead. Three full row arrays serve
  as the original, working copy and oracle in the harness. Peak process
  memory was not measured.
- Model `gpt-6.2-sol`. External paid compute spend was zero. Tokens, reasoning
  settings and session cost were not captured.

The recorded variant is closed for this flight replay. This fixes one boundary
of the earlier gain. A prospective application test needs batches with
corrections spread farther across the old order, and comparison with the
interval-limited merges alongside DeltaSort. [Reproduction commands](../../prototypes/agents/flight-key-corrections/README.md)
