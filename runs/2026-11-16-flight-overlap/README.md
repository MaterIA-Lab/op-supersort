---
title: Page reuse when real flight batches overlap
date: 2026-11-16 13:02
verdict: diagnostic
summary: The 36 monthly airport pairs had more than 99% of rows in the shared time interval. Even the longest single-source stretch was shorter than one page. Selecting each input's alignment nearly doubled median reusable coverage for lightly overlapping weekly batches.
model: Codex (exact model and reasoning settings not captured)
cost: not captured
idea: 1. Virtual memory as a data-movement engine
result: 0 eligible pages in 36 heavily interleaved pairs
baseline: Existing page-aligned inputs and output
closes: [whole-page reuse for the measured interleaved airport pairs]
opens: [independent starting offsets for near-disjoint runs prepared together]
how: A page of input can remain in place when all its rows are still together and fit a page in the merged order. We counted such pages in batches reconstructed from the departure times of 32,735 flights.
compared_with: We compared the existing page alignment with moving the start of the output and with placing each input at its own starting offset before writing it.
faster_where: All 36 heavily overlapping airport pairs had zero eligible pages. For the 20 weekly pairs with any overlap, choosing both input offsets raised median reusable coverage from 48.19% to 95.83%. This measures coverage under advance knowledge of both runs.
title_es: Reutilización de páginas al mezclar vuelos con horarios solapados
how_es: Una página de entrada puede quedarse en su sitio si todas sus filas siguen juntas y encajan en una página del resultado. Contamos esas páginas en lotes reconstruidos con los horarios de 32.735 vuelos.
compared_with_es: Comparamos la alineación habitual con desplazar el comienzo de la salida y con elegir dónde empieza cada entrada antes de escribirla.
faster_where_es: Ninguno de los 36 pares de aeropuertos con fuerte solapamiento tenía páginas reutilizables. En los 20 pares semanales con algún solapamiento, elegir dónde empezar ambas entradas elevó la mediana de cobertura del 48,19 % al 95,83 %. El cálculo supone conocer de antemano el orden de ambos lotes.
---

# Page reuse when real flight batches overlap

The [registered protocol](protocol.md) applies the merge geometry of the existing Linux candidate to 32,735 public NYC flight records. It reconstructs scheduled departure from the reported clock time and delay, then forms batches by actual departure. Every source row was retained. The supplied `hour` and `minute` agreed with the actual clock in all 32,735 rows and with the reconstructed schedule in 1,627. The test treats the date label as the service date and uses local wall time throughout.

| Workload | Pairs | Rows per pair | Any overlap | At least 5% of rows overlap | Median reusable with fixed alignment | Median with best output offset | Median with best independent input offsets |
|---|---:|---:|---:|---:|---:|---:|---:|
| Consecutive 7-day batches | 36 | 1,070–1,361 | 20 | 0 | 48.19% | 49.21% | 95.87% |
| Consecutive 1-day batches | 36 | 85–222 | 20 | 5 | 0% | 0% | 0% |
| Same-month feeds from different airports | 36 | 1,450–2,036 | 36 | 36 | 0% | 0% | 0% |

**Interleaved feeds.** The shared key interval contained 99.21–99.95% of the rows across the airport pairs. The longest consecutive stretch from either source had 17 rows. Even one 4 KiB page needs 32 of the modeled 128-byte rows. The maximum reusable size was zero even if the 64 KiB cutoff were reduced to one page.

**Adjacent batches.** Across the 20 weekly pairs with positive overlap, the fixed layout, best output offset and best independent input offsets had median coverage of 48.19%, 48.74% and 95.83%, respectively. The largest shared interval by row fraction contained 40 of 1,288 rows (3.11%). The two independent placements can align long stretches on either side of a short overlap when one output shift cannot align both. This is an optimistic ceiling that assumes the producer can choose each input buffer's offset before filling it. The largest one-day pair contained only 222 rows altogether, below the 512 rows in a 64 KiB extent.

No regime cleared the diagnostic's combined 5% overlap and 37.5% coverage screen. The rows from different airports expose a limitation of remapping interleaved data at the observed density. The weekly replay leaves a narrower use case where choosing input offsets during batch production could save a copy of much of both nearly ordered ranges. That output contract would need a denser workload and measurement of the planning and input preparation costs. This run measures page eligibility.

## Reproduce

```powershell
New-Item -ItemType Directory -Force -Path lab/flight-overlap | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/openintrostat/openintro/b37b235dd702363d5ad87af68dff9533cc148160/data/nycflights.rda' -OutFile lab/flight-overlap/nycflights.rda
python runs/2026-11-16-flight-overlap/probe.py lab/flight-overlap/nycflights.rda lab/flight-overlap
```

[Aggregated results](coverage.csv) · [Source hash and environment](metadata.json) · [Protocol](protocol.md)

The script uses the Python standard library and checks the pinned Git blob before parsing it. For all 108 cases it compares the merge against a stable sort and independently enumerates the eligible pages for all 32 offsets. It checks page and extent boundaries on 16 additional fixed-length pairs. The repository records aggregates. Per-flight rows and the original data stay in the local lab.
