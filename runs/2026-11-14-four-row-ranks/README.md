---
title: Stable rank inversion for four-record groups
date: 2026-11-14 15:57
verdict: failed
summary: Computing ranks and inverting them in AVX2 registers took 5–37% longer than the fastest direct SIMD reference on the primary batches. The extra work still cost time in the cache-resident control.
model: agent:gpt-6 (Codex)
idea: 5. Exact rank computation without data movement
result: 0.731–0.952× across two primary seeds
baseline: Best of the direct AVX2 compare-exchange network and shuffle lookup
closes: [four-record AVX2 shift-based rank inversion]
cost: not captured
---

# Stable rank inversion for four-record groups

Registered 2026-11-14 before implementing or timing the candidate.

## Workload and threshold

- Sort each group of four packed rows in place. A row is a little-endian 32-bit scalar with a 16-bit unsigned key in the high half and a 16-bit payload in the low half. Sort ascending by key, preserving input order at ties. Independent fixed groups model small batches of quantized candidates or local row IDs. This is a synthetic workload.
- Primary: 1,048,576 groups (16 MiB) with independent uniform keys. Controls: 8,192 groups (128 KiB) with uniform keys, and 1,048,576 groups with eight equally likely keys. Always use random payloads and both fixed seeds `31876423` and `720628791`. For correctness without timing, also enumerate all four-key sequences over the alphabet `{0, 1, 32768, 65535}` with distinct payloads, in a 257-group batch to exercise the odd tail.
- References: static Highway vqsort and x86-simd-sort per group using a key-and-slot representation to preserve ties, a direct five-comparator AVX2 network with position tags, and an independently implemented version of the six-comparison shuffle lookup described by Mimicry. Every routine receives the same ordinary packed records and includes any encoding, per-call storage and final writes. The candidate uses three pairwise vector comparisons, computes stable ranks for two groups at once, and inverts those ranks through byte-position shifts, OR reduction and an AVX2 permutation. The same scalar implementation serves any final unpaired group for the two-group kernels.
- One thread on logical CPU 8. Copy the input into the timed buffer outside measurement for every call. For the large cells use a 96 MiB cache eviction buffer after resetting the input. For the 128 KiB cell time the data while resident after the reset. Randomize method order within one warm-up and seven timed repetitions. Verify every call byte for byte against an independent `std::stable_sort` per group.
- Record the individual times and compare medians. The candidate must take at most 77% of the time of the fastest reference for both primary seeds to justify a broader evaluation. The project's reporting threshold applies to any finding of at least 1.5× on an important class. Controls diagnose the mechanism.

## Result

**Rejected.** In-register rank inversion beat the per-group library calls. The direct AVX2 baselines were faster on every cell when compared with the best reference for that input.

| Groups | Keys | Seed | Best reference | Best, ns/group | Rank, ns/group | Rank time / best time |
|---:|---|---:|---|---:|---:|---:|
| 1,048,576 | Uniform 16-bit | 31876423 | AVX2 network | 3.231 | 4.421 | 1.368× |
| 1,048,576 | Uniform 16-bit | 720628791 | AVX2 shuffle lookup | 3.430 | 3.601 | 1.050× |
| 8,192 | Uniform 16-bit | 31876423 | AVX2 network | 0.732 | 0.964 | 1.317× |
| 8,192 | Uniform 16-bit | 720628791 | AVX2 network | 0.610 | 0.793 | 1.300× |
| 1,048,576 | Eight values | 31876423 | AVX2 network | 4.879 | 6.702 | 1.374× |
| 1,048,576 | Eight values | 720628791 | AVX2 shuffle lookup | 5.366 | 9.905 | 1.846× |

The cache-resident control, which reduces the effect of transferring the input from memory, still took 30–32% longer than the network. The rank kernel uses a dependency chain of vector shifts and shuffles to derive the final permutation control. This is a plausible explanation for the cost in cache. The large cases show timing variability across rounds and between seeds, so the relative order of the two fastest references should not be generalized.

## Reproduction

- [Source and commands](../../prototypes/agents/four-row-ranks/README.md), [raw timing samples](raw.csv).
- AMD Ryzen 7 5800X, Windows 11 build 26200, logical CPU 8, one thread, GCC/MinGW-w64 16.1.0; flags are in the reproduction commands. Highway `a3f6f68fcc368e5e3025ca25805eabda9d8a456f` and x86-simd-sort `6e059b14975df2e3c74260ec905167a1be5a34ca` from the prior runner, both static AVX2. The direct AVX2 network and shuffle lookup are included in the source.
- Timing owns a 16 MiB input/output array in the large case; each paired kernel sorts in place in its loop, and the lookup has a 1 KiB read-only table. All methods additionally share 32 MiB of harness-owned source and expected output buffers and a 96 MiB eviction buffer. No hardware counters or peak residency samples were collected.
- All 240 benchmark calls, including 30 warm-ups, matched the stable reference exactly. All five methods also passed the untimed 257-group exhaustive batch. The benchmark uses synthetic packed layouts and did not measure application data or another ISA.

## Accounting

- Model: OpenAI GPT-6 (Codex session). The exact variant, token usage and per-run subscription cost were unavailable. No paid external compute was provisioned for this run.
