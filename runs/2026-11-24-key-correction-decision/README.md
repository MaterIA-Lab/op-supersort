---
title: Direct span moves against cache-buffered merging
date: 2026-11-24 00:25
verdict: failed
summary: A cache-buffered merge reduced the 128 MiB synthetic speedup to 1.004–1.137×. The prototype missed 1.30× in all 48 comparisons using real flight durations, so the project moves to another hypothesis.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 9. Move unchanged spans directly after a batch of key corrections
result: 1.004–1.137× on the 128 MiB synthetic check and 0.848–1.210× on the primary flight comparisons
baseline: Fastest median per case including two cache-buffered merges, four bulk merges, DeltaSort, both Rust full sorts and counting gather where applicable
closes: [direct span moves as an active research priority]
speedup: 0.848-1.210
how: The prototype plans the corrected order and moves each affected stretch directly into place. The new reference reads a small block of records into cache and merges corrections while it writes that block back.
compared_with: Two sizes of the new blocked merge, four earlier merges, DeltaSort and both Rust full sorts. The flight comparison also includes sorting by counting durations. All methods pay for temporary allocations.
faster_where: The prototype reached 1.004–1.137× on four fresh 128 MiB comparisons with random changes. The 64 MiB flight replay reached 0.848–1.210× with lookup by ID in the primary cache condition. No flight comparison reached 1.30×.
title_es: Movimiento directo de tramos frente a una fusión por bloques en caché
how_es: El prototipo calcula el orden corregido y mueve cada tramo afectado a su posición final. La nueva referencia carga un bloque pequeño en caché y fusiona las correcciones mientras lo vuelca a la posición de salida.
compared_with_es: Dos tamaños de la nueva fusión por bloques, las cuatro fusiones anteriores, DeltaSort y las dos ordenaciones completas de Rust. En vuelos se añade un método que cuenta registros por duración. Todos los métodos incluyen sus reservas temporales de memoria.
faster_where_es: En cuatro comparaciones nuevas de 128 MiB con cambios aleatorios, el prototipo obtuvo entre 1,004× y 1,137×. En 64 MiB de datos de vuelos, con búsqueda por ID, obtuvo entre 0,848× y 1,210× en la condición principal. Ninguna comparación de vuelos alcanzó 1,30×.
---

# Direct span moves against cache-buffered merging

**Decision. Move the research to another hypothesis.** The frozen prototype
still took less than half the time of the older references in the 128 MiB
random-replacement cases. A new reference merges within cache-sized blocks
and brought the measured advantage down to 1.004–1.137×. It also led the
references in all 48 flight comparisons. No flight window met the 1.30×
target in either cache state, with or without charging lookup by ID.
[Registered protocol](protocol.md) · [Reproduction](../../prototypes/agents/key-correction-decision/README.md)

## Synthetic screen

The 18 inputs cross three array sizes, three distributions of changes and
two seeds. Records are 128 bytes and the edit fraction is 0.098%. The
numbers give the minimum and maximum of the four ratios at each size and
displacement. Each ratio divides the best reference median by the median
of five measured direct-span calls on the same seed and cache state.

| Array | Short shifts | Medium shifts | Uniform replacement keys |
|---|---:|---:|---:|
| 4 MiB | 0.704–0.934× | 1.014–1.346× | 0.862–1.303× |
| 32 MiB | 0.599–0.780× | 0.947–1.258× | 0.874–1.385× |
| 128 MiB | 0.743–0.853× | 0.943–1.191× | 1.004–1.137× |

Short shifts had typical final displacements of 120–146 ranks. Medium
shifts had typical final displacements of 5,529–6,424 ranks. DeltaSort was
the fastest reference in every short-shift comparison. Four of 36 total
comparisons cleared 1.30×, and no size, displacement and cache combination
cleared it on both seeds.

In the four original-claim checks at 128 MiB, the prototype took
11.71–14.26 ms and the fastest blocked reference took 12.54–14.33 ms.
The best of the prior controls gave 2.030–2.249× on these same inputs.
The blocked reference wrote 0.9–2.4% more unchanged rows into the final
array than direct spans. It also copied rows into scratch. The phase
probe put planning at about 9% of the measured plan and execution time
in the 128 MiB random cases. The screen measures logical writes and wall
time. It does not identify physical DRAM traffic.
[Synthetic samples](synthetic.csv.gz) · [Synthetic build and timing metadata](synthetic-metadata.json)

## Flight duration reconciliation

January 2024 had 547,271 reports in the US Bureau of Transportation
Statistics [monthly archive](https://www.transtats.bts.gov/PREZIP/).
After excluding 21,901 cancelled or diverted records, the fixed roster
had 525,370 records and occupied 64.13 MiB. The benchmark uses the
reported scheduled and actual elapsed minutes, with modeled 128-byte
payloads. Scheduled local departure assigns each report to a batch.
Earlier scheduled buckets start with their durations reconciled. The
times represent a modeled schedule for receiving corrections. An input
clock of 24:00 goes in the next local day's midnight bucket.

The timed flight calls receive updates by dense row ID and read the
last-applied durations from a 2.00 MiB key array. They locate the original
position by binary search, apply the changes and update the key array.
All references use the same lookup. The diagnostic supplies positions
directly and also updates the key array.

| Batch | Edits, min–max | Median edits | Typical rank displacement | Median unchanged rows that move |
|---|---:|---:|---:|---:|
| 15 min | 212–451 | 249 | 25,734 | 489,962 |
| 60 min | 884–1,050 | 945 | 25,176 | 509,474 |

Typical displacement is the median across six windows of the median
absolute change in rank within each window. The median edit fraction is
0.047% for 15 minutes and 0.180% for 60 minutes. Each remaining row
whose final rank changes is written exactly once by direct spans.

| Input | Reset before timing | 15 min median ratio (range) | 60 min median ratio (range) |
|---|---|---:|---:|
| **Lookup by ID** | **Copy** | **0.979× (0.848–1.210×)** | **0.950× (0.886–1.041×)** |
| Lookup by ID | Copy and flush rows | 1.107× (0.960–1.192×) | 1.001× (0.860–1.015×) |
| Known positions | Copy | 1.063× (0.966–1.281×) | 0.997× (0.898–1.264×) |
| Known positions | Copy and flush rows | 1.127× (0.953–1.296×) | 1.018× (0.952–1.070×) |

Each table entry summarizes six window-level ratios. The buffered 32 KiB
and 128 KiB variants were the fastest references in 29 and 19 comparisons,
respectively. Against the earlier reference set alone, direct spans reached
1.525–2.256× in the 12 primary comparisons by ID. With the buffered
references included, zero of six primary windows passed for either width.
The registered April holdout required a pass in at least four January
windows of one width and was therefore skipped.
[Flight samples](january.csv.gz) · [Source archive digest and timing metadata](january-metadata.json)

## Verification and research implications

- All 4,860 measured calls and 1,944 warm-ups matched a separately stable
  sorted copy of the expected records, including persistent IDs, payloads
  and the updated per-ID state for flights. The harness also checks the
  minimum unchanged-row write count. A separate fixture sweep verified
  the frozen methods, five buffer sizes and the phase probe.
  [Verification log](verification.txt)
- AMD Ryzen 7 5800X, Windows 11 build 26200 and one thread pinned to
  logical CPU 8. The two stages were built separately with identical input
  sources, Rust 1.96.0 and optimization level 3 for `znver3`. The pinned
  DeltaSort revision, binary hashes and source hashes are in the metadata.
  Scratch allocation and release are timed. At 1,024 edits, the requested
  vector capacity is about 232 KiB for direct spans and 320 KiB for the
  32 KiB buffered control, without allocator and stack overhead. Peak
  process memory was not sampled.
- Earlier work schedules overlapping copies and defers new writes.
  The project specialization derives a schedule from the intact key
  order and covers unchanged rows with two ordered passes. The review
  leaves priority for that exact specialization open. The measured
  advantage over the strongest reference is below the project target in
  the main comparison. A new application that benefits from the smaller
  scratch requirement or reproduces a large speed advantage against the
  buffered reference could warrant reopening the line. [Prior-art review](prior-art.md)
- Model `gpt-6.2-sol`. External paid compute spend was zero. Token use,
  reasoning setting and model session cost were not captured.
