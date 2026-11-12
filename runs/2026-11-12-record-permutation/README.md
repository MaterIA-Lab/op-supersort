---
title: Record permutation headroom pilot
date: 2026-11-12 16:06
verdict: diagnostic
idea: 3. Payload permutation for records
summary: Gathering the payload takes 51–68% of an indirect sort of 64- and 128-byte records, so a permutation as cheap as a sequential copy would give about 1.3–1.4×. Enough room to try a candidate, with little margin.
result: 1.29–1.40× estimated headroom; 5/8 cases ≥1.3× on both seeds
baseline: fastest of vqsort + gather, x86-simd-sort + gather and pdqsort on rows
opens: [blocked permutation probe]
model: agent:gpt-6 (Codex)
cost: not captured
---

# Record permutation pilot — 2026-11-12

- **Author and model** `agent:gpt-6` (Codex session model family). Exact model variant, token count and billed model cost are unavailable to this session. The benchmark ran locally with no paid compute services.
- **Question** How much of a competitive sort of wide records is spent gathering the payload, and would replacing that phase with a sequential-copy cost leave enough room for a 1.3× end-to-end speedup?
- **State** Pilot complete. Five of eight workloads cleared the diagnostic threshold on both seeds. See [results](summary.md), [raw samples](raw.csv) and [machine and build metadata](metadata.json).

## Workload

- Contiguous records of exactly 64 or 128 bytes, aligned to a 64-byte cache line, with a `uint32_t` key, a unique `uint32_t` origin identifier and deterministic payload bytes.
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

## Reproduction

Run from the repository root with Python 3 and GCC on an AVX2-capable x86-64 machine running Windows or Linux. Supply a vendor directory with clean checkouts of [Highway](https://github.com/google/highway/tree/a3f6f68fcc368e5e3025ca25805eabda9d8a456f) and [x86-simd-sort](https://github.com/numpy/x86-simd-sort/tree/6e059b14975df2e3c74260ec905167a1be5a34ca) in matching subdirectories. For `pdqsort.h`, use the [snapshot in the repository archive](https://github.com/MaterIA-Lab/op-supersort/blob/195f5781c0a1ddbd0fba53db0e47b7b3a18c3555/prior-local/vendor/pdqsort.h). The runner verifies revisions and the header hash. The historical lab already has the same revisions. For the exact source of the original run, use `source_commit` in [metadata.json](metadata.json).

```sh
python runs/2026-11-12-record-permutation/run.py --vendor /path/to/vendor --output lab/record-smoke --cpu 4 --smoke
python runs/2026-11-12-record-permutation/run.py --vendor /path/to/vendor --output lab/record-pilot --cpu 4
python runs/2026-11-12-record-permutation/analyze.py lab/record-pilot/raw.csv
```
