# Bitplane membership sorting: preregistered kill test

Author: agent:gpt-6 (Codex). Registered before implementation and timing on 2026-11-22.

## Mechanism and prior art

Build eight 32-bit membership planes from 32 ordinary byte keys using AVX2
movemask. Refine a set of original positions by the next most significant plane.
Visit zero children before one children and enumerate equal-key leaves by
increasing source position. This produces a stable permutation without moving
keys or payloads during refinement. Materialize keys and payloads once.

Bit-sliced indexes and their top-k selection already exist (Rinfret, O'Neil and
O'Neil, SIGMOD 2001). SIMD bitwise MSB radix sorting also exists (Moeller, 2021).
Neither bit slicing nor radix partitioning is a novelty claim. The proposed
CPU mechanism to screen is retaining an entire short sort as scalar membership
masks after one vector bit transpose, with no per-level key/payload partition.
Its novelty relative to bitmap-index ordering is unconfirmed. A positive screen
would require a more specific novelty audit and stronger end-to-end references.

The potential gain is removing compare-exchange shuffles and payload movement
from intermediate stages. Risks are branch entropy, scalar mask traversal and
the final mask-to-permutation conversion. Unlike the closed four-row rank
experiment, this candidate does not compare each pair or invert numeric ranks.

## Workload declared before measurement

- Stable sorting of independent groups of 32 rows. Input and output are ordinary
  structure-of-arrays buffers: 32 uint8 keys and 32 uint32 payloads per group.
  Inputs are immutable; the caller provides separate reusable output buffers.
  Output has the same ordinary layout. No pre-existing bit-sliced input is given.
- Primary: 65,536 groups with uniform independent 8-bit keys, seeds 104729 and
  130363. These are kill-test development inputs, not held-out validation.
- Controls: 128 groups with uniform keys (resident), and 65,536 groups with
  eight equiprobable keys, the same seeds. The candidate always handles the
  entire 8-bit domain and does not receive a distribution selector.
- Before timing: all-equal, ascending, descending, alternating extrema, random,
  duplicate-heavy and single-outlier groups. Exhaustively embed all 4^4
  sequences over {0, 1, 128, 255} into four positions of 32-row groups.
  Use unique source-slot payloads as well as random payloads to verify ties.

## References, timing and decision rule

- Direct fully batched AVX2 bitonic network on 16-bit key/position tags, followed
  by the same output contract. Include tag construction and materialization.
- Highway vqsort and x86-simd-sort on 32-bit key/position tags, and a simple
  stable counting sort on the entire byte domain. Include encoding, counts,
  prefix sums, temporary storage initialization and materialization.
- Use existing pinned Highway a3f6f68fcc368e5e3025ca25805eabda9d8a456f and
  x86-simd-sort 6e059b14975df2e3c74260ec905167a1be5a34ca. Record compiler, flags,
  source hashes and hardware with the results. The direct network is not a
  per-array library call; every method processes the entire batch in one call.
- One thread pinned to logical CPU 8 on the Ryzen 7 5800X. Explicitly flush
  input and output cache lines with CLFLUSH and a fence before each large trial.
  Resident controls omit flushing. Initialize and allocate harness buffers
  outside timing for every method. Per-group scratch on the stack is timed.
- One warm-up and seven measured rounds, with deterministically shuffled method
  order. Record every sample and verify keys AND payloads byte for byte against
  an independent per-group std::stable_sort after every timed call.
- Kill the implementation if candidate median is above 77% of the fastest
  reference median on either primary seed. Do not tune on those inputs and then
  call them holdouts. No change of the primary class after seeing timings.
- Proceed to fresh validation only if both primary seeds pass. A finding of at
  least 1.5x on an important class must be reported to the owner before broad
  exploration continues. A primitive win alone does not establish a finding.

## Sources

- https://www.cs.umb.edu/~poneil/SIGBSTMH.pdf
- https://www.ti.uni-bielefeld.de/downloads/publications/simdRadixSort.pdf
- https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SEA.2021.3

## Accounting

Model: GPT-6 (Codex); exact deployment variant and reasoning settings unavailable.
Tokens and subscription cost are not captured. No external paid compute is
planned for this local screen.
