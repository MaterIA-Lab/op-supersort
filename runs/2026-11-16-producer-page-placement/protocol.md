# Producer-side placement for a stable merge

Registered 2026-11-16 before implementation or timed measurement.

## Contract

Both independently produced batches and one stable merged output are required. All three must be contiguous read-only arrays of the same 128-byte record, backed by fresh memory. The producer provides two sorted, mutable working buffers already in RAM. It may reuse them after the call. Implementations may share backing pages between their new read-only batches and the merged view. These three outputs have one lifetime. Given equal keys, left-batch rows precede right-batch rows and each batch keeps its original order. The consumer uses the merged output immediately.

## Matrix

- Primary: chronological pairs with roughly 2% of rows in a shared key range, at nominal combined sizes of 1,048,576 and 2,097,152 rows (128 and 256 MiB). For each size let `half = nominal_rows / 2`. Use `half + 13` and `half - 1` source rows in the first seed, and `half + 19` and `half + 4` in the second. Thus the second batch's unshifted source phase differs from its destination phase and both merged outputs have trailing partial pages.
- Controls, using the same smaller size, offsets and seeds: disjoint ranges, and fully interleaved ranges. Synthetic shapes use the edge-overlap level observed in the independent OpenIntro flight diagnostic as motivation. These are newly generated layouts rather than repeated real flight records. For edge overlap, take `floor(left_rows / 50)` and `floor(right_rows / 50)` from their touching ends and shuffle the merge sides inside the overlap using `std::mt19937_64`. The fully interleaved control uses the same side shuffle over the whole pair. Increasing keys include pairs of equal keys at a fixed cadence to exercise stability.
- The primary seeds are `4316079` and `99237281`. Include untimed edge checks for all-equal data, empty runs, reverse order and a contained range, and source and destination sizes on both sides of a page boundary. Smoke uses 8,205 and 8,191 rows, seed 109, all three distributions and one non-reported repetition. These are correctness checks and remain outside the timing evidence.
- Native Windows, ordinary 4 KiB pages, AMD Ryzen 7 5800X, one thread pinned to logical CPU 8. Evict approximately 96 MiB before each invocation. Run one verified warm-up and five timed rounds per input, shuffling method order per round from the input seed. No concurrent heavy workloads started by the harness.

## Methods and accounting

- Direct references include fresh batch copies followed by a hybrid bulk/linear merge, and a fused producer that writes each row to its batch and its merged position during one traversal. Include both cached and AVX2 non-temporal stores for the fused writer. The hybrid can copy the long outer stretches in bulk. The strongest reference is the fastest of these three methods per cell.
- The candidate uses binary searches on both endpoints to find stable outer stretches, reserves the final virtual interval and reuses only full aligned spans of at least 64 KiB. Compare a plan with zero source offsets to the independently placed plan. Both charged paths calculate the plan, write the two batches, map the output, copy the gap and tail, and make all three results read-only.
- Include planning, fresh allocation and first touch, input materialization, mapping or copying the merge, all fences, making the buffers read-only and the first consumer sweep of one 64-bit word per cache line. Exclude generation, eviction and correctness checking. Report batch construction, output assembly and sweep separately. Teardown is measured after verification, outside the primary time. Verify every batch and all merged bytes against an independent stable `std::merge`, including warm-ups.
- The candidate advances if its median total time is at most 77% of the fastest direct reference for **both seeds at both primary sizes**. Report the fixed-versus-independent alignment difference, including mapped bytes, even if the direct threshold fails. A pass warrants a fresh test on the Linux implementation and real oversized batches before a project finding. A miss closes this particular Windows implementation under the tested output contract.

## Accounting

Codex via ChatGPT. Exact model variant, tokens and marginal provider cost were unavailable. No external compute was provisioned.

## Generator correction

The preliminary executable drew the merge side with equal probability until one run ran out, which left an unusually long single-source tail in the interleaved control. The registered shuffle was implemented as sampling without replacement using the number of remaining rows on each side. The complete matrix was rerun with the original sizes and seeds, and the preliminary measurements were discarded. The final CSV records the observed overlap count for every call.
