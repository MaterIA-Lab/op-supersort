# Sort key groups with exceptions inside a source block

Author: agent:gpt-6.2-sol (Codex). Registered on 2026-11-24 before
implementing or timing the methods.

## Contract

Stably sort immutable 64-byte records by an existing parallel uint32 key
column. Each result is a complete contiguous array of records in a reused
output buffer. Equal keys retain input order. Input keys span the complete
32-bit domain. The sort begins with cold input and output cache lines on
one pinned Ryzen 7 5800X thread. Time scratch allocation and release,
key inspection and tag creation, sorting, record copies and the final
store fence. Keep fixture preparation, output reservation and exact
verification outside the timer.

## Mechanism and references

- **Masked block.** For groups of up to 64 input rows, choose one key
  from the first, middle and last positions, taking a repeated value
  when present and the first otherwise. AVX2 equality yields one mask
  of its matching rows. Create one sortable tag for the group and one
  per nonmatching row. Expand the mask into consecutive source spans
  after sorting. Charge the creation, storage and traversal of the masks.
- **Run-length reference.** Use AVX2 to find equal-key runs by comparing
  each key to its predecessor. Sort one tag per contiguous run and
  recover its length from the next recorded boundary.
- **Per-record reference.** Sort one tag per original row and copy
  the referenced rows to the output.

Test each encoding with pinned Highway VQSort on unsigned 64-bit tags
and a stable four-pass byte radix on the 32-bit key. All three encodings
use the same source prefetch distance, coalescing of adjacent source
spans in the final order, and 64-byte streaming output writer. Every
method writes the returned payload once. The mask is an attempt to
reduce the tags sorted when exceptions fragment an otherwise repeated
key. Record tag counts, output span counts, scratch capacities, and
prepare, sort and output diagnostics.

## Inputs and timing

- Primary inputs comprise 524,288 and 2,097,152 records (32 and
  128 MiB). Generate successive burst lengths uniformly from 96 to
  287 with SplitMix64. Choose an independent uniform 32-bit base key
  per burst. Replace each key independently with a fresh uniform
  32-bit draw with probability 1/8. Burst boundaries are independent
  of the 64-row encoding blocks. Use development seeds 39281 and 87407.
- Use the same seeds in three 32 MiB controls. Test bursts with no
  replacements, bursts with probability 1/4, and independent uniform
  keys with no bursts. These model sensitivity to fragmentation.
- Run GCC 16.1 with `-O3 -march=znver3`, Highway at
  `a3f6f68fcc368e5e3025ca25805eabda9d8a456f`, and logical CPU 8.
  Flush cold buffers before timing. Use two warm-ups and seven
  measured rounds with shuffled method order. Run heavy benchmarks
  sequentially. Poison and verify the full output on every call.
  Preflight covers empty inputs, equal and distinct keys, ties
  between ordinary and group tags, and partial mask blocks.

## Gate

Use the fastest reference median in each primary case, including both
sorters with per-record tags and equal-run tags. A single mask variant
must take at most 77% of reference time in all four primary cases. If
both pass, select the one with the better worst-case speedup, favoring
VQSort on a tie. Freeze the sources and executable and repeat the two
sizes on fresh seeds 135527 and 219517. A successful screen would
justify an audit against actual key columns and further related work.

Model gpt-6.2-sol in Codex. No external compute spend is planned.
Mark unavailable token, setting and session cost data as unavailable.

## References

- [Abadi, Madden and Ferreira, Integrating Compression and Execution in Column-Oriented Database Systems](https://doi.org/10.1145/1142473.1142548)
- [Lemire and Boytsov, Decoding billions of integers per second through vectorization](https://arxiv.org/abs/1209.2137)
- [Inoue and Taura, SIMD- and Cache-Friendly Algorithm for Sorting an Array of Structures](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf)
- [Blacher et al., Vectorized and Performance-Portable Quicksort](https://arxiv.org/abs/2205.05982)
