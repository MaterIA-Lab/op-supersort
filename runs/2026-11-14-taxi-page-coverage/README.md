---
title: Page reuse in completed taxi-trip batches
date: 2026-11-14 16:11
verdict: diagnostic
summary: Only one of twelve weekly pairs overlapped in pickup time. Four rows of that pair fell inside the overlap, and choosing the output offset did not increase its page reuse.
model: agent:gpt-6 (Codex)
idea: 1. Virtual memory as a data-movement engine
result: 1/12 weekly pairs overlapped and 0/12 put at least 5% of rows in the overlap
closes: [small seaborn taxi sample for overlapping merge timing]
opens: [dense completed-trip replay with substantial overlap]
cost: not captured
---

# Taxi-trip batches and page reuse

Registered 2026-11-14 before processing the input or computing coverage.

## Question

The [previous GH Archive probe](../2026-11-12-gharchive-page-coverage/README.md) found disjoint timestamp ranges. Measure how many aligned slices survive genuinely overlapping event-time ranges using real trip times and a reproducible batch rule. Also measure the best result a sorter could get by choosing the output buffer's offset within a page from the merge plan.

## Input

- Use the March 2019 NYC taxi trip sample distributed with [seaborn-data](https://github.com/mwaskom/seaborn-data/blob/71e2436a092d714350de0fc409ca8a8714e7e78f/taxis.csv) at revision `71e2436a092d714350de0fc409ca8a8714e7e78f`, blob `ded045b462d361b8a0e5ddcdd6c3361cce4ddab4`. Keep duplicates, drop missing or invalid timestamps and rows whose completion precedes pickup, and report the counts. Interpret the published clock fields as local wall time. The public [NYC TLC description](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) documents pickup and completion times.
- Group rows by the date the trip finished, then sort each batch by pickup time. This models rewriting completed-trip batches by start time. The two timestamps are observed trip times. Completion-based batch membership is a chosen replay rule, and the source has no ingestion logs.
- Use midnight boundaries on March 8, 9, 15, 16, 22 and 23. The primary pair at each boundary contains the seven full calendar days leading up to it and the seven full days following it, with no shared rows in a pair. Controls use one day on either side at each boundary. Cases share parts of the same source and are not independent. Use all twelve, including disjoint or empty cases.

## Geometry and decision

- Model two page-aligned input runs of fixed 128-byte records, 4 KiB base pages, and the same 64 KiB minimum extent as the earlier probe. Stable order keeps the original source row order within each batch at equal pickup times and places the earlier batch first at a tie.
- Use the prior probe's grouped merge geometry and independent row-by-row check for page-aligned output. Compute the 32 possible output offsets by assigning every eligible source slice to the offset that matches its position. Verify the aligned total against the prior implementation and the other offsets with a separate explicit page-by-page enumerator over the stable row merge.
- Report overlap, rows, and fractions for the existing aligned-output contract and the best single output offset. The offset changes the returned pointer alignment from page alignment to 128-byte alignment and may need extra boundary copies, space and a planning pass. Coverage takes precedence over timing such a change.
- Promote this data source to a timing follow-up only if at least two of the six weekly pairs have strictly overlapping pickup ranges and at least 37.5% mappable bytes at a 64 KiB minimum. Evaluate the existing and selectable offset layouts against this rule independently. The public sample is smaller than the earlier timing workloads, so a pass only warrants a larger source with the same semantics. The diagnostic measures geometry and supplies no performance estimate.

## Follow-up protocol registered after the midnight check

All six weekly midnight pairs and all six daily controls were disjoint. The follow-up uses the same dates and batch durations but places the boundary at 12:00 local time to model a change of shift during active service. The noon boundaries were registered before computing their coverage. Report both rounds. For every case also count how many rows from the two batches fall within their shared pickup-time interval. In addition to the original coverage screen, require at least 5% of output rows within that shared interval in at least two qualifying weekly pairs to prioritize a larger overlapping merge benchmark with these batch semantics.

## Result

All 6,433 parsed records had both times in order. Of the twelve weekly pairs across midnight and noon, only the pair at noon on March 23 had positive pickup-time overlap. Four of its 2,793 rows lay within the shared 1,537-second window (0.14%). Page coverage was 50.41% for both the current layout and the best selectable offset. In the daily control for the same boundary, four of 409 rows overlapped and zero bytes qualified under the 64 KiB extent cutoff. All other daily controls were disjoint.

The largest improvement from choosing an offset was 2.12 percentage points among the weekly pairs. It occurred in a disjoint case. Neither the current layout nor the selectable offset met the original coverage and overlap gate. The only overlapping weekly case also missed the follow-up minimum of 5% overlapping rows. The sample is too sparse to use as an overlapping merge benchmark. The next data source for this question should have substantially denser batches and event-time overlap. This test measured layout eligibility without running a sorting performance comparison.

## Reproduction

The [24-case coverage table](coverage.csv) and [source metadata](metadata.json) contain aggregates. The probe checked the unshifted result against the prior geometry and all 32 offsets against a page-by-page traversal of the stable merge. After the noon follow-up, all columns from the original midnight run reproduced exactly. The source file remains under the ignored `lab/` directory.

```powershell
New-Item -ItemType Directory -Force -Path lab/taxi-page-coverage | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/mwaskom/seaborn-data/71e2436a092d714350de0fc409ca8a8714e7e78f/taxis.csv' -OutFile lab/taxi-page-coverage/taxis.csv
python runs/2026-11-14-taxi-page-coverage/probe.py lab/taxi-page-coverage/taxis.csv runs/2026-11-14-taxi-page-coverage
```

The probe checks the exact source blob and uses the repository's GH Archive coverage code. It uses only the Python standard library.

## Accounting

- Model: OpenAI GPT-6 (Codex session). The exact variant, token usage and per-run subscription cost were unavailable. No paid external compute was provisioned for this run.
