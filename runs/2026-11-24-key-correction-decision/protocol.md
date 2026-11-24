# Direct-span decision experiment

Author: agent:gpt-6.2-sol (Codex). Registered on 2026-11-24 before building
the comparison harness, extracting the flight data, or timing any inputs.

## Question

The frozen direct-span prototype beat the previous references on large arrays
with about 0.1% independent random key replacements. The three published real
replays missed the project target. The Lichess minute batches approached the
synthetic edit density, with a 2.44 MiB array and around 181 ranks of typical
displacement. Vary size and displacement independently and add a
cache-buffered merge reference. Test the same candidate on a real workload
with sparse batches, more than 32 MiB of rows and potentially large rank
changes. The candidate itself is unchanged.

## Registered synthetic screen

- Use the prior fixed-length, same-address update contract. Original rows
  are sorted by `(uint32 key, persistent uint32 id)`. The caller supplies
  known source positions and unapplied replacement keys. The rows are
  128 bytes each. Use 4, 32 and 128 MiB with 32, 256 and 1,024 edits,
  respectively. At each size use seeds 48781 and 90271. Generate initial
  rows and payloads with SplitMix64 and select unique edit positions by
  partial Fisher–Yates. Keep the original rows and edit positions identical
  across the three displacement modes within a size and seed.
- For the short and medium modes, draw a direction and an absolute old-rank
  offset uniformly from 1–256 or 4,096–8,192, respectively. Clamp at the
  boundaries and use the old key at that rank. For the random mode, use
  independent uniform32 replacement keys. Record actual final rank
  displacement, shifted unchanged rows and the covering interval.
- The main screen is the 128 MiB random-replacement cells as the original
  claim check. The other cells map the boundary of the tested gain.
  Record each size and displacement even when it misses the threshold.

## Registered real data

Use the US Bureau of Transportation Statistics [Reporting Carrier
On-Time Performance monthly archive](https://www.transtats.bts.gov/PREZIP/),
January 2024 for development and April 2024 for holdout. Use one row per
non-cancelled, non-diverted report with valid flight date, scheduled
gate-departure time, scheduled elapsed minutes and actual elapsed minutes.
Keep the set of rows fixed and assign dense IDs in source CSV order.
Payloads are modeled at 128 bytes. The source first ranks flights by
scheduled elapsed minutes and persistent ID. For each named window,
assume reports in earlier scheduled departure buckets have already been
reconciled, then replace scheduled with actual elapsed minutes for rows in
the window. Net no-ops are omitted. Dates and scheduled clocks are the
reported local departure buckets. This is a scheduled-bucket reconciliation
replay. These fields do not give the time when a correction was received.
Roster construction filters to complete reported flights.

In each month select the 9th and 13th at 07:00, 12:00 and 17:00, with
half-open windows of 15 and 60 minutes at each start. Keep every window.
Report geometry even for an empty batch. Record the archive hashes, row
count, edit density, actual rank displacements, interval and minimum
unchanged writes. Use the first month as the measurement screen if its
roster occupies more than 32 MiB. Keep the source ZIPs and row snapshots
local. The measured operation receives edits by ID and the old key
per ID from the replica state. Inside the timer find the original
positions in the still-sorted array, allocate the edit list, apply and
reorder, update the old-key state and release scratch. Use the same lookup
path for all methods. Measure a supplied-positions version on the same
inputs as a diagnostic. Verify sorted rows and updated ID-key state.

## Methods and timing

- Frozen direct spans, pinned upstream DeltaSort at
  `89322c7bfb8d5b28b179650d08249398cbe0a977`, both Rust full sorts
  and both bulk extract-sort-merge directions with and without limiting the
  interval. For bounded duration keys include the counting and prefetched
  gather from the FIDE experiment.
- Add a forward block-buffered extract-sort-merge. Save and sort corrected
  rows before overwriting. Load blocks of old rows into a cache-sized
  buffer, compact out removed rows, then merge clean spans and replacements
  into the main array in order. Keep pending originals in scratch when
  the writer reaches the read boundary. Use both 32 and 128 KiB tile sizes
  as independent references. Skip stationary prefixes when the read and
  write cursors align and scratch is empty. Charge all staging and scratch.
  This control keeps the two materialization steps near each other so the
  intermediate payloads can remain in cache.
- Time whole calls after a copy reset alone and after a copy reset followed
  by CLFLUSH and MFENCE. On the same Windows host, pin one thread to logical
  CPU 8 and use rustc optimization level 3 with `target-cpu=znver3` and one
  codegen unit. Shuffle method order and alternate the cache states randomly
  each round. Measure five repetitions after two warm-ups in each cell.
  For direct-span phase diagnostics, separately measure an instrumented
  copy with timestamps immediately before executing its planned moves and
  at completion. Exclude this version from the race. Verify the whole
  output on every call against an independently stable-sorted snapshot.
  Record source and binary hashes, logical writes and scratch capacities.
  Keep other heavy work off the benchmark host during the timings.

## Decision rule

Compare each candidate median with the fastest reference median for the
same input and conditions. Report whether the 128 MiB random result still
clears 1.30× on both fresh seeds in each cache state. Keep any synthetic
evidence tied to its conditions and reference set.

For real validation use the ID-based call and copy-reset state as primary.
A window width qualifies for April holdout if at least four of six January
windows measured 1.30× or more. Validate a qualifying width by the same
rule on the independently registered April windows. A failure in January
closes that replay without timing April. Publish both cache states and
the supplied-positions diagnostic. Four of six comparisons is the
decision criterion for this specific replay.

Continue toward a dedicated implementation only if the frozen candidate
passes a real holdout and the prior-art review supports a specific
algorithmic contribution. Otherwise close or defer this line as a research
priority, recording where the benefit survives, any remaining credible
use case, and what evidence could justify reopening it. A source-access
failure is recorded as missing evidence. Restrict the performance claim
to the workloads actually tested. Audit the scheduling against DeltaSort
and Burns and Long's in-place delta reconstruction, which orders bulk
copies to avoid overwriting unread data.

Model gpt-6.2-sol in Codex. No external paid compute planned. Record token
usage and cost as unavailable if the provider does not supply them.
