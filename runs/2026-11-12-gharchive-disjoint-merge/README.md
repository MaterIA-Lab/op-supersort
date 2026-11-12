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
---

# Page remapping on GH Archive batch sizes

- [Registered protocol and reproduction](protocol.md#reproduction)
- [Results and limitations](summary.md)
- [Raw measurements](disjoint.csv)
- [Machine, build and source revision](metadata.txt)
- [Source archive manifest and verified page coverage](../2026-11-12-gharchive-page-coverage/README.md)
