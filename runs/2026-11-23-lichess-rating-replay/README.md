---
title: Refreshing Blitz ratings from Lichess games
date: 2026-11-23 23:27
verdict: failed
summary: On 24 batches of real Blitz ratings for 19,982 accounts, direct span moves took 13–21% longer in the typical comparison. DeltaSort was the fastest reference in 45 of 48 comparisons.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 9. Move unchanged spans directly after a batch of key corrections
result: 0.827–0.881× median reference time divided by direct-span time. 0 of 48 comparisons passed.
baseline: Fastest median of DeltaSort, four bulk merges, both Rust full sorts and counting with prefetched gathering
closes: [direct span moves for the tested historical Blitz rating refresh]
speedup: 0.827-0.881
how: Reconstruct the latest reported Blitz rating for each account from game records. Apply one or ten minutes of changes by moving affected stretches of the sorted array directly into place.
compared_with: DeltaSort, four ways of compacting and merging records, both Rust full sorts, and counting by rating followed by copying rows into order. Every method includes its temporary allocations.
faster_where: On a 2.44 MiB array of 19,982 accounts, direct spans took 13–21% longer than the best reference in the median of each condition. DeltaSort led the references in 45 of 48 comparisons. No comparison reached 1.30×.
title_es: Actualización de una clasificación de blitz con partidas de Lichess
how_es: Se reconstruye la última puntuación de blitz observada de cada cuenta a partir de las partidas. El prototipo aplica los cambios de uno o diez minutos moviendo los tramos afectados directamente a su posición final.
compared_with_es: DeltaSort, cuatro variantes de compactación y fusión, las dos ordenaciones completas de Rust y una variante que cuenta fichas por puntuación y las copia en orden. Todos los métodos incluyen la memoria temporal que reservan.
faster_where_es: En un array de 2,44 MiB con 19.982 cuentas, el prototipo tardó entre un 13 % y un 21 % más que la mejor referencia en la mediana de cada condición. DeltaSort fue la referencia más rápida en 45 de 48 comparaciones. En ninguna se alcanzó el objetivo de 1,30×.
---

# Refreshing Blitz ratings from Lichess games

Sparse batches on a small array still favored DeltaSort. The direct-span
prototype reached 0.827–0.881× by the median of the window-level speed ratios
in four workload and cache conditions. None of the 48 comparisons met the
registered time limit. All 6,048 sorter calls matched the expected output.
[Registered protocol](protocol.md) · [Reproduction](../../prototypes/agents/lichess-rating-replay/README.md)

## Input and movement

Reconstruct the latest pre-game rating observed for each account using the
[January 2015 Lichess rated standard game archive](https://database.lichess.org/standard/lichess_db_standard_rated_2015-01.pgn.zst).
The fixed roster comprises 19,982 accounts that appeared in a rated Blitz
game before January 22. Its 128-byte modeled records occupy 2.44 MiB. The
source was scanned for 648,250 rated Blitz game headers, of which 542 lacked
a valid January UTC timestamp. The test uses twelve fixed start times and
refreshes ratings with the net observations from half-open windows of one
and ten minutes each. All windows contain changes.

The replay approximates a sorted replica of last observed ratings. It uses
recorded pre-game ratings, game timestamps and modeled payloads. It holds
roster membership fixed, and each benchmark call starts with original row
positions and unapplied updates. Source parsing and position lookup happen
before timing.

| Batch | Edits, range | Edits, median | Median across windows of typical edited rank displacement | Median affected interval, rows | Median unchanged rows that must move |
|---|---:|---:|---:|---:|---:|
| 1 minute | 10–52 | 26 | 181 | 17,761.5 | 4,774 |
| 10 minutes | 84–353 | 209.5 | 182 | 19,694 | 13,452 |

Typical edited rank displacement is the median absolute difference between
each edited row's initial and final rank within a window. The largest
individual displacement was 9,680 ranks. The frozen prototype made the
minimum possible number of unchanged-row writes in every window. These
are logical writes, meaning rows copied in the array, rather than measured
cache-line traffic. The broad affected intervals coexist with relatively
short typical displacements. The experiment timed whole calls and did not
isolate the cost of planning the moves.
[Aggregate measurements and archive digest](aggregate.json)

## Timing results

Choose the best reference by its median in each window and cache state.
Take the median of those pairwise speed ratios across the twelve windows
in each row of the table. Each median per method uses eleven calls after
three warm-ups. The prototype and all references include planning, applying
changes, and allocating and freeing temporary memory.

| Batch | Reset before timing | Median speed ratio | Range across windows | Windows passing the 77% time limit | Windows with DeltaSort as fastest reference |
|---|---|---:|---:|---:|---:|
| 1 minute | Copy and flush | 0.841× | 0.728–1.039× | 0/12 | 12/12 |
| 1 minute | Copy | 0.851× | 0.728–1.167× | 0/12 | 12/12 |
| 10 minutes | Copy and flush | 0.827× | 0.772–0.909× | 0/12 | 12/12 |
| 10 minutes | Copy | 0.881× | 0.752–1.018× | 0/12 | 9/12 |

A ratio below 1 means the prototype took longer than the reference.
In five comparisons the prototype finished sooner than the fastest
reference by median. The largest gain was 1.167×. Two right-compacting
full-array merges and one right-compacting interval-limited merge led the
references in the three cases where DeltaSort did not lead.

## Verification and accounting

- All 4,752 measured calls and 1,296 warm-ups matched a separately sorted
  copy, including every key, persistent ID and payload word. Python and
  Rust agreed on the affected interval and on the exact minimum unchanged
  writes in each window.
- The prototype was unchanged from the synthetic experiment. DeltaSort was
  built from `89322c7bfb8d5b28b179650d08249398cbe0a977`. The nine methods
  ran on one thread pinned to logical CPU 8 of an AMD Ryzen 7 5800X,
  Windows 11, using rustc 1.96.0 and `-C opt-level=3 -C target-cpu=znver3 -C codegen-units=1`.
- Vector capacities for the candidate are at most 80 KiB at 353 edits
  on the 64-bit build, excluding allocator and stack overhead. Three
  full arrays are kept outside the timer for original, working and
  expected rows. Peak process memory was not measured.
- Model `gpt-6.2-sol`. External paid compute spend was zero. Model
  token use, reasoning setting and session cost were not captured.
- The original timing archive and per-window geometry were saved under
  `lab/2026-11-23/lichess-rating-replay/` before local tool access failed.
  This entry publishes the recovered aggregate measurements. The
  reproduction commands generate complete sample files on a supported host.

This screen closes the tested small-array replay. The larger synthetic
cases used random replacement keys and arrays of 128 and 256 MiB.
[Large-array measurements](../2026-11-23-key-correction-spans/README.md)
