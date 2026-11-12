---
title: GH Archive page coverage
date: 2026-11-12 18:25
verdict: diagnostic
summary: All eight registered archive pairs had disjoint event-time ranges. Between 48.25% and nearly 100% of the modeled bytes can be remapped, so these inputs measure assembly of preordered ranges and leave overlap untested.
model: OpenAI GPT-6.1 Sol, Extra High
idea: 1. Virtual memory as a data-movement engine
result: 8/8 pairs passed 37.5% coverage; 0/8 had timestamp overlap
opens: [timing against two bulk copies on the archive batch sizes]
cost: not captured
---

# GH Archive page coverage

The [registered protocol](protocol.md) tested eight pairs of sorted batches drawn from eight hourly [GH Archive](https://www.gharchive.org/) files. The files contained 1,629,949 event rows, counting duplicate events as separate rows. The source archive metadata reports 734,358,304 compressed bytes and zero invalid JSON rows or timestamps. The [archive manifest](archives.json) records URLs, SHA-256 digests, aggregate counts, time bounds and the analysis source commit. The [coverage CSV](coverage.csv) contains the full pair matrix.

Every event timestamp was within its file's labeled UTC hour. The ranges had no shared timestamps and each pair yielded exactly two consecutive source slices in ascending order. Six pairs could map only the first batch's full-page interior. The second batch could reuse pages only when the first batch's row count was divisible by 32, the number of 128-byte rows per 4 KiB page. Two pairs met that alignment condition. Displayed percentages are rounded. The largest remappable extent was 59,875,328 bytes.

All eight grouped merge plans matched an independent row-by-row stable merge. The preregistered gate passed on both dates. The next run times all eight batch sizes against bulk concatenation, treating them as a real batch-size workload for a contiguous output. Actual overlapping arrivals still need a source with different batch and event-time boundaries. [Timing protocol](../2026-11-12-gharchive-disjoint-merge/protocol.md)

## Reproduction

Run from the repository root with Python 3. Downloads stay under the ignored cache. The report command uses the published aggregates and requires no downloads.

```sh
python -X utf8 runs/2026-11-12-gharchive-page-coverage/probe.py --self-test
python -X utf8 runs/2026-11-12-gharchive-page-coverage/probe.py --cache lab/gharchive --output lab/gharchive-page-coverage --fetch
python -X utf8 runs/2026-11-12-gharchive-page-coverage/probe.py --report runs/2026-11-12-gharchive-page-coverage/coverage.csv
```

## Pair table


| Capture date | UTC batches | Events | Timestamp-range overlap | Full source pages | Same phase | Mappable | Extents |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025-01-15 | 08 → 09 | 467,801 | 0.0 s | 99.99% | 48.29% | 48.29% | 1 |
| 2025-01-15 | 09 → 10 | 480,271 | 0.0 s | 100.00% | 100.00% | 100.00% | 2 |
| 2025-01-15 | 10 → 11 | 463,201 | 0.0 s | 99.99% | 51.46% | 51.46% | 1 |
| 2025-01-15 | 08-09 → 10-11 | 931,002 | 0.0 s | 100.00% | 50.24% | 50.24% | 1 |
| 2025-01-18 | 08 → 09 | 348,649 | 0.0 s | 100.00% | 48.25% | 48.25% | 1 |
| 2025-01-18 | 09 → 10 | 352,321 | 0.0 s | 100.00% | 51.21% | 51.21% | 1 |
| 2025-01-18 | 10 → 11 | 350,298 | 0.0 s | 99.99% | 99.99% | 99.99% | 2 |
| 2025-01-18 | 08-09 → 10-11 | 698,947 | 0.0 s | 99.99% | 49.88% | 49.88% | 1 |

Timing gate passed. 2/2 dates had a pair with at least 37.5% mappable bytes.
