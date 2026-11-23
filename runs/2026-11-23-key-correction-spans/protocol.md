# Direct span moves after key corrections

Author: agent:gpt-6.2-sol (Codex). Registered on 2026-11-23 before implementing or timing the experiment.

## Contract

One thread applies a batch of `(original_position, replacement_key)` edits
and returns the sorted rows at the same base address. The caller supplies a
contiguous array in original ascending `(uint32 key, uint32 id)` order and a
read-only list of edits in arbitrary order, with at most one valid position
per row. IDs are unique persistent tie breakers. A row is 128 bytes and
contains 15 uint64 payload words in addition to its key and ID. The exact same
original array and unapplied edit list are available to all methods. The caller
does not maintain a separate key index or supply insertion ranks. The timed
operation includes sorting the edit list, applying the edits, all planning,
allocation and deallocation of per-call scratch, and output writes.

This models an in-memory sorted read replica receiving tracked corrections to
a timestamp or score. The primary workload uses the independent random
replacement model in the DeltaSort paper. Every workload is synthetic. The
array is sorted before the call and every method applies the new keys itself.
Filtering updates or collecting them from another system is outside the call.

## Registered inputs

Generate old keys, full payloads, an unsorted random sample of distinct source
positions and new keys deterministically with SplitMix64. Original keys are
independent uniform32 and the original rows are sorted by `(key, id)` outside
timing. The new keys in uniform cases are independently uniform32. The local
control uses the old key at a randomly chosen offset in `[-256, 256]` from each
source position, clamped at the array ends. Compare ties by persistent ID.

| Stage | Rows | Edits | New keys | Seeds |
|---|---:|---:|---|---|
| Development primary | 1,048,576 | 1,024 | Uniform32 | 84731, 190027 |
| Development control | 1,048,576 | 32 | Uniform32 | 84731, 190027 |
| Development control | 1,048,576 | 1,024 | Local | 84731, 190027 |
| Development control | 4,096 | 16 | Uniform32 | 84731, 190027 |
| Holdout primary | 1,048,576 | 1,024 | Uniform32 | 1000003, 16777259 |
| Holdout primary | 2,097,152 | 2,048 | Uniform32 | 1000003, 16777259 |

## Methods

- **Direct spans** saves the updated rows and sorts them by the replacement
  order. It binary-searches their insertion gaps in the still intact original
  array, scans the edits and gaps to plan spans and replacement destinations,
  then moves left-shifting spans in ascending order and right-shifting spans
  in descending order. It writes the saved rows last. The prototype is
  described in [idea 9](../../notes/ideas.md#9-move-unchanged-spans-directly-after-a-batch-of-key-corrections).
- **Bulk ESM left** saves and sorts the same updated rows. Compact clean rows
  to the left in contiguous copies and merge from the right using binary
  searches for contiguous output spans. Give it the same edit preprocessing
  and `copy_within` primitives as the candidate.
- **Bulk ESM right** uses the mirrored strategy. Compact rightwards and merge
  forwards. Both orientations can skip rows already at the correct address
  in each phase.
- **DeltaSort** calls the author's Rust implementation via `delta_sort_by`
  at `89322c7bfb8d5b28b179650d08249398cbe0a977`. Patch the input keys and collect
  the dirty index array inside the timing. Use the same `(key, id)` comparator.
- **Full sort** applies the edits and calls Rust's `sort_unstable_by_key` on
  rows. The unique total order gives the same output as the other methods.

## Timing and decision rule

One benchmark executable built with rustc 1.96.0, `-C opt-level=3 -C
target-cpu=znver3 -C codegen-units=1`. Pin to logical CPU 8 on the Ryzen 7
5800X with Windows 11. Restore the working array outside timing and explicitly
flush its cache lines, with an MFENCE, in the large cells. Keep the 4,096-row
control resident. Run one warm-up and seven measured rounds. Shuffle method
order within every round using a separate generator. Verify every whole row,
including payload, against patching and independently sorting a copy before
timing. Check edge cases on separate fixtures before the first timed trial.
Do not run other heavy jobs alongside the measurements.

Record all times and the number of unchanged rows written by the candidate
and both bulk ESM methods. These counters count logical writes into the main
array and exclude updated rows. They do not estimate physical memory traffic.
Report median total times and per-round wins. Advance to the fixed holdout
matrix only if the candidate takes at most 77% of the fastest reference's
median on both development primary seeds. Freeze code and build before the
holdout. Require all four holdout cells to clear the same gate for a speed
claim on this declared class. Report evidence of at least 1.5x in the primary
class to the owner and pause broad exploration. This benchmark can establish
the speed and movement counts under its contract. A claim of novelty needs
additional prior-art review. A user-facing release needs broader validation.

No external paid compute is planned. Model `gpt-6.2-sol` in Codex. Token usage,
reasoning setting and session cost are not captured.
