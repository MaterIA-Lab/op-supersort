# Reordering departure records after schedule corrections

Author: agent:gpt-6.2-sol (Codex). Registered on 2026-11-23 before running the replay.

## Question and input

Direct span moves saved time with independent random key replacements. Test the
same implementation on a departure board that gives each flight its reported
departure minute as it departs. Most flights should move less than a random row
in a year-long array. The effect on elapsed time is unknown.

Use all 32,735 records in the pinned OpenIntro NYC flight sample. Reuse the
project's existing reader and reconstruct the scheduled minute from the delay
and reported departure clock under the source service date. Set the actual
minute to scheduled minute plus reported delay. This reuses the prior protocol
for assigning dates across midnight. A 128-byte record consists of a minute key,
the stable source row number, and deterministic synthetic payload. Only timing
keys and batch composition come from the flight data. Record and verify the
source blob and the replay input digest. [Dataset and clock checks](../2026-11-16-flight-overlap/README.md)

## Replay and timing boundary

Model a daily flush of completed departures at midnight in local wall time.
Immediately before a day starts, rows for earlier departures use actual time.
Rows for other departures still use scheduled time. Sort that snapshot by
`(key, source row number)` and supply positions for every flight whose actual
departure is in the day and differs from its schedule. Supply those edits in
actual departure order, using source row number at ties. Keep the year-sized
array fixed across cases. Snapshot construction and position lookup are fixed
inputs outside the timed operation, as in the registered random-correction test.
This is a replay of actual timestamps under a modeled delivery schedule.

Preselect all seven days from the first Monday of January, April, July and
October 2013. They are January 7–13, April 1–7, July 1–7 and October 7–13.
Run each of the 28 day batches twice, with copy reset followed by explicit
CLFLUSH/MFENCE of the input array and with copy reset alone. The array is
about 4 MiB and fits in the 5800X last-level cache. One warm-up round and seven
measured rounds per day and cache regime. Use a permutation of method order
per round, one thread pinned to CPU 8, and the same Rust optimization profile
and DeltaSort pin as the random-correction experiment. Time all in-call edit
planning, allocation, writes and frees. Exact-compare every record to an
independently sorted snapshot for the end of the day. Verify the candidate's
unchanged-row write count against positions in that oracle.

## Comparisons and decision rule

- Frozen direct span moves, both full-array bulk ESM directions, unmodified
  DeltaSort, and Rust's adaptive stable and unstable full sorts from the
  [previous experiment](../2026-11-23-key-correction-spans/README.md).
- Two additional bulk ESM controls that restrict compaction and merge to one
  affected interval. Enclose all replaced rows and ranks of the smallest
  and largest replacement in the original order, then run the corresponding
  bulk merge on that slice. Charge searches and edit position conversion.
  This is a coarse interval around the registered edits and an ordinary merge
  baseline. The candidate's displacement plan remains unchanged.

Use the fastest reference median for each day and cache regime. For a class
claim, require at least 21 of the 28 days at 77% of best reference time or
less in each regime. Report the median and range of day-level ratios and the
number of passing days in both regimes. Also report edit count, rank distances,
and logical writes and how they differ from independent random corrections.
Label any gain by regime and workload. Use local compute only. Model
`gpt-6.2-sol`. Reasoning setting, token use and session cost are not captured.
