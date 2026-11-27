---
title: Reusing packed rank groups across sliding windows
date: 2026-11-27 13:55
verdict: failed
summary: Keeping already packed indices between adjacent windows was slower than packing them again, even though only one or two groups changed. The fastest cached variant ran at 0.647–0.950× the speed of the best reference on the main inputs.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 14. Reuse packed rank groups across sliding windows
result: 0.647–0.950× on primary inputs across two passes
baseline: Fastest verified median across independent sorts, incremental sorted arrays and stateless extraction from a shared sorted union
closes: [cached packed rank groups for 32- and 64-element sliding windows]
speedup: 0.647-0.950
how: Sort the combined inputs of several adjacent windows once. Keep the active indices in packed groups of eight ranks, and rebuild only the groups affected by the departing and arriving indices.
compared_with: Sorting each window by itself, editing the previous window's sorted order, and sorting a shared union once and packing the active indices again for each window.
faster_where: Both cached variants lost on 131,072 synthetic windows of 32 or 64 keys. Packing again from the shared order was the fastest reference at width 32. Updating a small sorted array with streaming output stores was fastest at width 64.
title_es: Reutilizar grupos de índices ordenados entre ventanas deslizantes
how_es: Ordenar de una vez los datos compartidos por varias ventanas consecutivas. Guardar en grupos compactos los índices de cada ventana y actualizar solo los grupos donde entra o sale un índice.
compared_with_es: Ordenar cada ventana por separado, actualizar el orden anterior, y ordenar los datos compartidos y volver a compactar los índices en cada ventana.
faster_where_es: Las dos variantes quedaron por detrás en 131.072 ventanas sintéticas de 32 o 64 claves. Con 32 claves ganó volver a compactar las posiciones. Con 64 ganó actualizar una lista pequeña y escribir la salida directamente.
---

# Reusing packed rank groups across sliding windows

**Decision. Close cached packing for the tested sliding windows.**
Neither store variant reached the 77% time limit in any of the four
primary comparisons, in either pass. The same two seed pairs were
used in both passes. The conditional holdout was skipped.
[Registered protocol](protocol.md) · [Prototype and build instructions](../../prototypes/agents/rolling-rank-chunks/README.md)

## Full sort timings

All methods emit stable absolute indices for every one of 131,072
overlapping windows. Each median covers seven complete calls after
two warm-ups. The ratio divides the fastest reference median by the
faster cached variant's median in that row. The two candidate variants
were also checked individually against the decision rule.

| Pass | Width | Seed | Fastest reference | Ref., ms | Cached candidate, ms | Stream candidate, ms | Best ratio |
|---|---:|---:|---|---:|---:|---:|---:|
| Initial | 32 | 83179 | Shared union, pack again | 2.064 | 2.409 | 2.189 | 0.943× |
| Initial | 32 | 152083 | Shared union, pack again | 2.090 | 2.751 | 2.200 | 0.950× |
| Initial | 64 | 83179 | Incremental, streaming stores | 3.850 | 5.946 | 6.993 | 0.647× |
| Initial | 64 | 152083 | Incremental, streaming stores | 3.859 | 5.266 | 6.817 | 0.733× |
| Repeat | 32 | 83179 | Shared union, pack again | 1.835 | 2.412 | 2.291 | 0.801× |
| Repeat | 32 | 152083 | Shared union, pack again | 1.855 | 2.350 | 2.173 | 0.854× |
| Repeat | 64 | 83179 | Incremental, streaming stores | 3.888 | 5.182 | 6.550 | 0.750× |
| Repeat | 64 | 152083 | Incremental, streaming stores | 3.860 | 5.142 | 6.346 | 0.751× |

The same reference won at each width with 16 distinct key values.
The fastest cached variant reached 0.825–0.863× at width 32 and
0.697–0.764× at width 64 across the duplicate-key controls.
[Initial samples](initial/development.csv) · [Repeat samples](repeat/development.csv)

## What the references showed

The comparison with stateless packing holds the union sort, membership
updates, shuffle table and cached output policy fixed. Retaining the
packed vectors adds a refresh after each changed mask and loads the
stored vectors and counts again when emitting the next window. Across
all 16 cases, retaining the vectors took 1.024–1.406× as long as
packing again. These are full-call timings and leave the individual
costs of refresh and reload unmeasured.

At width 32, sharing the sorted union and packing again ran at
1.395–1.589× the speed of the fastest incremental reference on the
uniform inputs and 1.558–1.625× on the 16-key controls. At width 64,
its uniform ratio against the incremental reference fell to
0.744–0.820×. This is a comparison between references on the registered
synthetic inputs. It gives a reason to include stateless union packing
in future short-window comparisons.

## Verification and accounting

- All 1,008 measured calls and 288 warm-ups matched an independent
  `std::stable_sort` of the indices in every window. Each build also
  verified 720 fixture calls, including unsigned boundaries, ties,
  incomplete groups of windows and the end of the output buffer.
  [Initial verification](initial/verification.txt) · [Repeat verification](repeat/verification.txt)
- Both builds ran on one pinned Ryzen 7 5800X thread under Windows 11
  build 26300, compiled with GCC 16.1 and Highway at
  `a3f6f68fcc368e5e3025ca25805eabda9d8a456f`. The repeat guards an already
  defined Windows macro to remove a compiler warning. It keeps the
  same algorithm, inputs and timing boundaries.
  [Initial build metadata](initial/development-metadata.json) · [Repeat build metadata](repeat/development-metadata.json)
- The input is about 512 KiB. The caller's index output is 16 or 32 MiB.
  The candidate's declared tile buffers total at most 2.29 KiB,
  excluding library stack and bookkeeping, plus a shared 8 KiB shuffle
  table. The independent verification array, cache flushes and buffer
  setup are outside timing. All methods pay for their preprocessing
  and output writes, and streaming stores are fenced before timing ends.
- External paid compute spend was zero. Model tokens, reasoning setting
  and session cost were uncaptured.
