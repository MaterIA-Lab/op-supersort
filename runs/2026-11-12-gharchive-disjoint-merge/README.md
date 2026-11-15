---
title: Page remapping on GH Archive batch sizes
date: 2026-11-12 18:34
verdict: promising
summary: On eight disjoint pairs with batch sizes and order derived from GH Archive, remapping beat every fresh-output reference. It beat the resident-buffer references in the two cases where almost all pages could be mapped. Real overlapping arrivals remain untested.
model: OpenAI GPT-6.1 Sol, Extra High
idea: 1. Virtual memory as a data-movement engine
result: 1.431–7.252× fresh (7/8 ≥1.5×); 2/8 resident ≥1.5×
baseline: fastest of scalar, galloping bulk, hybrid and two-copy concatenation for fresh output; hybrid and two-copy concatenation for resident output
opens: [test overlapping batches from a source with independent arrival and event clocks]
cost: not captured
speedup: 1.431–7.252
how: Timed the remapping approach on the 8 real batch sizes and orders from GH Archive (with synthetic keys and payloads), against every reasonable way of building a fresh output, including simply concatenating with two memcpy calls.
compared_with: Fresh output: plain, galloping and hybrid merges and a two-copy concatenation. Separately: hybrid and two-copy into a buffer that already exists in memory.
faster_where: 1.43–1.66× faster when about half the pages can be mapped, and 6.7–7.3× when almost all can (7 of 8 cases at 1.5×). Against a buffer already in memory it only wins in the two nearly fully mapped pairs (1.66–1.74×); otherwise 0.38–0.49×. Only batches that do not overlap in time were tested.
title_es: Remapeo de páginas con lotes de GH Archive
how_es: Se cronometró el remapeo con los 8 tamaños y órdenes de lote reales de GH Archive (con claves y contenido sintéticos), frente a todas las formas razonables de construir una salida nueva, incluida concatenar con dos llamadas a memcpy.
compared_with_es: Salida nueva: mezclas clásica, galopante e híbrida y concatenación con dos copias. Aparte: híbrida y dos copias hacia un buffer que ya está en memoria.
faster_where_es: 1,43–1,66× más rápido cuando se puede mapear cerca de la mitad de las páginas, y 6,7–7,3× cuando casi todas (7 de 8 casos llegan a 1,5×). Frente a un buffer que ya está en memoria solo gana en los dos pares casi totalmente mapeables (1,66–1,74×); en el resto, 0,38–0,49×. Solo se probaron lotes que no se solapan en el tiempo.
---

# Page remapping on GH Archive batch sizes

- [Registered protocol and reproduction](protocol.md#reproduction)
- [Results and limitations](summary.md)
- [Raw measurements](disjoint.csv)
- [Machine, build and source revision](metadata.txt)
- [Source archive manifest and verified page coverage](../2026-11-12-gharchive-page-coverage/README.md)
