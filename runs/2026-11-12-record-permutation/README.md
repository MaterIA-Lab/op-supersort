# Record permutation pilot — 2026-11-12

- **Author and model** `agent:gpt-6` (Codex session model family). Exact model variant, token count and billed model cost are unavailable to this session. No paid compute is planned. The benchmark runs locally.
- **Question** How much of a competitive sort of wide records is spent gathering the payload, and would replacing that phase with a sequential-copy cost leave enough room for a 1.3× end-to-end speedup?
- **State** Protocol registered before timing. Results pending.

## Workload

- Contiguous records of exactly 64 or 128 bytes with a `uint32_t` key, a unique `uint32_t` origin identifier and deterministic payload bytes.
- Ascending, unstable sort on the key, with an immutable input and a fully materialized, contiguous output in RAM. Every original record must appear exactly once with its payload intact.
- Two sizes, 1,048,576 and 4,194,304 records. The primary synthetic inputs model full-width randomly ordered keys and randomly ordered 12-bit keys with duplicates. Use SplitMix64, taking the high 32 bits of each key draw and masking to 12 bits for the latter distribution. The payload uses a separate deterministic stream.
- Seeds 271 and 1601. One warm-up and three measured repetitions per method and seed. Rotate method order between repetitions and seeds. Use one thread on the project owner's Ryzen 7 5800X and record the OS, compiler, flags, CPU affinity and exact reference revisions.

## Methods and timing

1. Pack `(key, source index)` into a `uint64_t`, sort the packed words with Highway vqsort or x86-simd-sort AVX2, and gather complete rows in sorted-index order. Record allocation and packing, index sort, output allocation and gather, and the full elapsed time separately.
2. Copy the input into the destination, then sort complete rows by key with pdqsort. Include allocation and copying. This is a direct competitive reference for the pilot. A follow-up seeking a project finding must also evaluate IPS⁴o and account for the closest record-oriented work from the literature.
3. Allocate a destination and copy the same input bytes sequentially. This is a diagnostic for the cost of materializing the output.

Prepare the input outside timing and touch a 64 MiB eviction buffer before each trial. Include temporary allocations, packing, payload writes and disposal of temporary index storage in end-to-end timing. Return the output to the caller. Verify every warm-up and measured output outside timing by checking key order, unique source IDs and complete equality with the corresponding source record. For the copy diagnostic, check byte-for-byte equality with the source array. Record wall-clock samples and peak process memory, including the benchmark's verification workspace, along with the method-specific buffer sizes.

## Decision before implementing a candidate

For each paired repetition and each indirect reference, estimate `indirect total − gather phase + sequential copy`. Divide the fastest actual sort time among the three references by the smallest of those estimated times. Take the median ratio over repetitions within each seed. Continue only if at least one size, width and distribution reaches 1.3× on **both** seeds. Publish the full matrix. The sequential-copy estimate is an optimistic diagnostic, with uncertainty from cache state and allocation. A pass justifies a candidate experiment and a deeper novelty review. Any later performance claim needs measured end-to-end candidate times on fresh inputs.
