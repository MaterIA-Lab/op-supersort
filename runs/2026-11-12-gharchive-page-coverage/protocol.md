# GH Archive page coverage protocol — 2026-11-12

- **Model** OpenAI GPT-6.1 Sol, Extra High, as identified by the owner. Local processing has no incremental cloud compute charges. Token count and billed model cost are unavailable in the session.
- **Question** Do adjacent, naturally captured batches of public events preserve enough page-aligned slices after sorting by event time to justify timing the remapped merge on them?

## Registered inputs

Use GH Archive's hourly capture files for **2025-01-15** (Wednesday) and **2025-01-18** (Saturday), hours **08, 09, 10 and 11 UTC** on each date. Use every event with a valid top-level UTC `created_at`. Report excluded rows and preserve duplicates. Keep the original capture-file membership even when an event's recorded time falls outside the capture hour. Publish the source URLs, compressed-file digests and aggregate counts. Keep downloads and per-event data under `lab/`. [GH Archive](https://www.gharchive.org/)

For each day, compare the adjacent hourly pairs **08|09**, **09|10** and **10|11**, plus **08–09|10–11** as two pooled capture batches. These eight pairs share input files within a date. The two dates are convenience samples for a weekday and weekend, with no statistical claim about the archive as a whole. Include every registered pair in the report. Mark a missing source explicitly if it cannot be recovered.

## Measurement

Sort each batch by `created_at`, preserving file and line order for ties within a batch. In a merge, equal timestamps from the earlier capture batch come first. Grouping equal timestamps into counts is lossless for page geometry under this ordering because the records have a fixed width. Model the prior 128-byte record, page-aligned source and destination, 4 KiB base pages, and minimum 64 KiB mapping size. Input construction, real payload widths and memory backing are separate from this diagnostic. The archive supplies timestamp patterns and batch boundaries.

Walk maximal consecutive slices taken from the same source in the merged order. For each, count full source pages in the slice and the subset with matching source and destination offsets modulo the page size. Count bytes, extents and largest extent when the matched interior meets the 64 KiB minimum. Independently verify each batched merge plan against a row-by-row stable merge of the source timestamp counts. Report source rows, overlap between the timestamp ranges, and the mappable fraction. The result measures coverage without inferring a speedup.

## Decision

Time the existing prototype on these timestamp layouts only if at least one registered pair **on each date** has **at least 37.5%** of its bytes mappable under the current cutoff. That fraction is the smallest one that cleared 1.3× in the prior fresh-output synthetic probe. It is a screen for potential, with sizes and overlap patterns that may differ from the prior run. If the gate passes, include all eight pairs in the timing protocol with the existing fresh-output and resident-buffer references. If it fails, record which condition failed and retain the measurement as evidence about this workload. [Prior candidate](../2026-11-12-page-remapped-merge-candidate/summary.md)
