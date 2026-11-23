---
title: Updating a chess ranking with monthly FIDE ratings
date: 2026-11-23 01:39
verdict: failed
summary: The frozen direct-span prototype reordered 464,388 FIDE rating records 1.18-1.23× as fast as Rust's unstable full sort, the fastest reference. All 252 calls were correct. Neither cache condition reached the 1.30× target.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 9. Move unchanged spans directly after a batch of key corrections
result: 1.178-1.230× against Rust's unstable full sort on the June to July 2024 transition
baseline: minimum median across DeltaSort, four bulk compaction and merge variants, stable and unstable Rust full sorts, and counting with a prefetched gather
closes: [the 1.30× gate on the registered FIDE development pair]
speedup: 1.178-1.230
how: Compare the FIDE standard chess rating lists for June and July 2024. Keep players rated in both months. Move stretches of unchanged records directly into their final positions before placing the records with new ratings.
compared_with: DeltaSort, four ways to compact and merge, stable and unstable Rust sorting, and a reference that counts records by rating and gathers them into order. All methods pay for temporary allocations.
faster_where: The prototype finished in 23-24 ms on 464,388 records with 29,726 rating changes. Rust's unstable sort took 27-29 ms and was the fastest reference. The measured gain of 1.18-1.23× fell below the 1.30× target in both cache conditions.
title_es: Reordenación de la clasificación de ajedrez de la FIDE
how_es: Se comparan las listas oficiales de junio y julio de 2024 y se conservan las fichas presentes en ambas. El prototipo calcula el nuevo orden, mueve cada tramo de fichas sin cambios hasta su posición final y coloca las que tienen una puntuación nueva.
compared_with_es: DeltaSort, cuatro variantes de compactación y fusión, la ordenación estable e inestable de Rust y una variante por conteo de puntuaciones. Se incluye la reserva de memoria auxiliar de todos los métodos.
faster_where_es: Al actualizar 29.726 puntuaciones entre 464.388 fichas, el prototipo tardó 23-24 ms y la mejor referencia, la ordenación inestable de Rust, 27-29 ms. La mejora de 1,18-1,23× quedó por debajo del objetivo de 1,30× en las dos condiciones de caché.
---

# Updating a chess ranking with monthly FIDE ratings

The frozen prototype returned correct results on a real ranking with
widespread changes. It missed the preregistered speed threshold. Rust's
unstable full sort was the fastest reference in both cache conditions.
[Protocol](protocol.md) · [Reproduction](../../prototypes/agents/fide-rating-updates/README.md)

## Registered development pair

Use the standard rating lists for June and July 2024 from the [official FIDE archive](https://ratings.fide.com/download_lists.phtml).
The ZIP member name and the rating column heading are checked against the
requested month. There are 464,401 rated entries in June and 468,009 in
July. Their intersection contains 464,388 distinct players. None of the keys
used for matching was ambiguous. The 13 departures and 3,621 additions are
outside this fixed-membership task.

There were 29,726 rating changes (6.40%). The array was 56.69 MiB with 128-byte
rows. Keys are the actual published ratings. The harness uses synthetic
payloads and a deterministic identifier tie-break. The caller has already
matched IDs and supplied positions before the timer starts. This measures
maintaining order in an array with known updates using a single month pair.
[Source hashes and aggregate distributions](geometry.json)

| Input geometry | Measured value |
|---|---:|
| Median displacement of a changed record | 9,666 ranks |
| 95th percentile displacement | 48,325 ranks |
| Maximum displacement | 201,524 ranks |
| Rows inside the affected interval | 464,386 |
| Unchanged rows that must move | 433,710 of 434,662 (99.78%) |

## Timing results

Times in milliseconds are medians of 11 calls after three warm-ups per
method and cache state. Copy reset alone leaves the cache state produced by
copying. The array is larger than last-level cache. The other condition
flushes the reset array explicitly with CLFLUSH and MFENCE. Both charge the
entire apply-and-sort operation, including auxiliary allocation and frees.

| Method | Reset and flushed, ms | Reset by copy, ms | Unchanged-row writes into the array |
|---|---:|---:|---:|
| **Direct span moves** | **23.517** | **23.010** | 433,710 |
| Rust unstable full sort | 28.920 | 27.109 | — |
| Counting with prefetched gather | 33.123 | 31.967 | — |
| Full-array ESM, compact right | 45.497 | 46.799 | 869,324 |
| Full-array ESM, compact left | 48.080 | 54.860 | 869,320 |
| Interval-limited ESM, compact right | 53.582 | 46.213 | 869,320 |
| Interval-limited ESM, compact left | 50.700 | 50.484 | 869,320 |
| Rust stable full sort | 88.748 | 85.494 | — |
| Original DeltaSort | 94.817 | 91.535 | — |

Direct spans took 18.7% less time after flushing (1.230×) and 15.1% less
after copy reset (1.178×) than Rust's unstable sort. It won 11 of 11 and 10 of
11 paired measured rounds respectively. Both medians missed the 77% time
limit. The candidate wrote the exact minimum number of unchanged rows,
49.9% of the writes requested by each compaction and merge reference. That
saving was enough to beat all four such references. The fastest benchmark
reference was a full sort. The measured differences cover one observed edit
density and rating distribution at a fixed record width.
[Raw samples](raw.csv) · [All medians and ranges](summary.json)

## Verification, resource use and costs

- All 198 measured calls and 54 warm-ups matched a separately sorted oracle
  in every rating, identifier and payload word. A Python geometry pass and
  the Rust harness independently agreed on the minimum unchanged-row writes.
  The logged move counts are logical writes. No physical memory traffic was
  sampled.
- AMD Ryzen 7 5800X, Windows 11 build 26200, logical CPU 8, one thread, Rust
  1.96.0 targeting `znver3`. Original DeltaSort from
  `89322c7bfb8d5b28b179650d08249398cbe0a977`. The direct-span source matches
  both prior runs. [Build hashes, flags and environment](metadata.json)
- At 29,726 edits, the prototype's vector capacities request at most
  6,896,456 bytes. The interval-limited merges request up to 5,231,776 bytes.
  The counting reference uses a full-row temporary array and compact indices.
  Its largest concurrently live capacities total about 61.82 MB. These
  figures omit stack and allocator overhead. The harness keeps three full
  arrays outside the timer. Peak process memory was not sampled.
- Model `gpt-6.2-sol`. External paid compute cost was zero. Model tokens,
  exact reasoning setting and session cost were not captured.

The prototype already minimizes movement of unchanged rows in this contract.
Testing a lower-density ranking workload requires genuine smaller batches
with known prior positions. A monthly pair alone does not verify a general
ranking speedup.
