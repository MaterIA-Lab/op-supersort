# Reordering a chess ranking after a monthly update

Author: agent:gpt-6.2-sol (Codex). Registered on 2026-11-23 before inspecting
rating changes or timing the methods.

## Input and workload

Use FIDE's complete standard rating lists for June and July 2024. This is a
development pair for checking whether the synthetic gain on widely scattered
key corrections transfers to changes in a ranking. The flight replay used
smaller arrays and most corrections moved records by only a few positions.

- [Official download archive](https://ratings.fide.com/download_lists.phtml)
- [June 2024 list](https://ratings.fide.com/download/standard_jun24frl.zip)
- [July 2024 list](https://ratings.fide.com/download/standard_jul24frl.zip)

Read the fixed-width lists and use only the FIDE number and the standard
rating. Match rated entries by number and take the intersection of the two
monthly populations. Record the size of each list, counts entering and leaving,
and the number of rating changes. Remap numbers to dense identifiers in
ascending number order for the fixture. Keep the source files and the
converted row-level input local. Publish hashes, aggregate geometry and
timings with no player-level data.

The original array holds the June ranking in `(rating, id)` order, ascending.
The oracle uses the July ratings of the same players, with the same tie order.
One batch supplies every changed July rating and its prior position in
ascending identifier order. Each 128-byte record has 15 words of deterministic
synthetic payload. The candidate receives the previously published
input contract. Matching entries, finding positions and producing the oracle
are outside the timer. Insertions and deletions of players are outside this
fixed-membership task.

## Analysis and decision rule

First record edit fraction, the distribution of edited rows' absolute rank
displacements, both old and new rank coverage, and the fraction of unchanged
rows whose final rank differs from the original. Compare the exact minimum
unchanged-row writes with the four compact-and-merge controls. The number of
rows that change ranks measures the geometry of the real rating update.

If at least 100,000 rated players can be matched without ambiguous IDs, time
the complete batch in both cache states. Use copy reset before each call and
CLFLUSH/MFENCE after reset in the flushed case. Use three warm-up and eleven
measured rounds in each state, with shuffled method and cache-state order.
Use one thread pinned to logical CPU 8 on the same Ryzen 7 5800X as the flight
run. Include allocating and freeing scratch, all key/rank computation, edits,
and moving rows. Compare every key, identifier and payload word against the
independent oracle after every call. Also check the candidate's write count
against the exact minimum for unchanged rows.

## Competitive references

- Frozen direct spans and the references used in the flight replay: upstream
  DeltaSort, Rust stable and unstable full sort, and bulk extraction-sort-merge
  in both directions with either full-array or affected-interval scope.
- A counting-based reference for the narrow integer domain. Count rows per
  rating and save the rating and physical source position by dense identifier.
  Scatter source positions into rating buckets in identifier order, gather
  records into a temporary array, then copy back into the original address.
  Prefetch both cache lines of the source 32 records ahead during the gather.
  Charge the full temporary array and all compact index buffers.

Compare the median to the fastest reference median in each state. The screen
passes only at 77% of the fastest reference time or less in both conditions.
If fewer than 100,000 rows match, report geometry only. Even a timing pass is
development evidence on one observed transition. It needs independent monthly
holdouts for a class claim. Report a measured speedup of at least 1.5× to the
owner before continuing broader exploration. Use local compute and log actual
engineering costs where known.
