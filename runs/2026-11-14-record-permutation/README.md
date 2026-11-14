---
title: Record permutation by source band
date: 2026-11-14 15:37
verdict: failed
summary: Grouping reads by source band took about 23% longer on the primary batch. Preparing the groups and moving rows together took longer than reading ahead in the original layout.
model: agent:gpt-6 (Codex)
idea: 3. Payload permutation for records
result: 0.814× across two primary seeds
baseline: Fastest measured indirect sort with software prefetch
closes: [histogram grouping within destination windows]
cost: not captured
---

# Record permutation working-set test

Registered 2026-11-14 before implementing or timing the candidate.

The [2026-11-12 blocked probe](../2026-11-12-blocked-permutation/summary.md) had already closed sorting each window's descriptors by source. This work was started from a stale local checkout. It tests the cheaper histogram-based grouping in place of a per-window sort, smaller rows and a resident destination.

## Workload

- Primary: 8,388,608 contiguous 16-byte records (32-bit unsigned key, original 32-bit ordinal, payload), one CPU thread, Windows x86-64 and AVX2. Stable ascending order into a separate, preallocated caller-owned destination. Input and output buffers are already resident. Keys are independent uniform 32-bit values used as a synthetic proxy for fixed-width database rows.
- Controls: 1,048,576 records at 16 bytes and 8,388,608 records at 64 bytes. Use the same input seeds for paired comparisons: `174630147` and `876321419`. `std::mt19937_64` generates keys. Each row's ordinal is unique, and payload words are deterministically derived from that ordinal.
- Smoke inputs, for checking the executable before the measured run: 31 and 65,537 records, both widths, seed `5731`. The large smoke input exercises a partial destination window and source band. Smoke measurements will not drive parameter changes.

## Procedure

- Baselines: pack `(key, ordinal)` and sort with Highway vqsort, then gather into final output (plain and software lookahead of 16, 32 or 64 rows). Include vqsort plus 32-row lookahead and aligned non-temporal output stores, and x86-simd-sort plus 32-row lookahead. Try the local IPS2Ra/IPS4o snapshots as a packed radix reference and a direct row reference respectively when their Windows sequential APIs build. Include ska_sort as a direct row radix reference. Use a plain contiguous `memcpy` of the original rows as an optimistic materialization timing control.
- Candidate: same vqsort key encoding, with 65,536 output records per window and 4,096 input records per source band. Use a histogram plus prefix sums and a second metadata pass to group one packed `(offset, slot)` request per row. Read source bands in order and scatter directly within the output window. Time all of this, including scratch creation and destruction.
- Time total duration and the available phases within the same call. Include allocating, filling and releasing every per-algorithm buffer, all conversions, and writing the final output. Exclude generation, caller-owned storage, cache preparation, and verification. Pin to logical CPU 8 for both the setup and measurement inside the benchmark process. Reset cache state approximately with a 96 MiB read before each run. Do one verified warm-up and five measured rounds per cell, with algorithm order shuffled deterministically within each round. Report medians and individual samples.
- Verify the full bytes of every output, including warm-ups, against an independent ascending `std::sort` of `(key, ordinal)` followed by materialization. Check `memcpy` separately against the original source. Reject the run on any mismatch.
- For each primary seed let `T` be the quickest median end-to-end reference. For the candidate's existing vqsort-based approach, estimate the time with idealized materialization as `T_vq - G_vq + C`, where `G_vq` is the gather median and `C` is the sequential copy median. This is a measured planning estimate, not a lower bound. If that estimate exceeds `0.77 * T` on either primary seed, the candidate lacks enough headroom with this sort front end. Regardless of the estimate, advance this implementation to a wider evaluation only if it actually takes at most `0.77 * T` on both primary seeds. Controls diagnose the outcome and cannot rescue the gate.

## Result

**Rejected.** The grouped schedule was slower in all six cells. The primary case took about 267 ms with grouping versus about 218 ms for the best measured reference. Medians are from five rounds per cell and exclude the warm-up.

| Rows | Row bytes | Seed | Best reference | Best, ms | Grouped, ms | Time relative to best |
|---:|---:|---:|---|---:|---:|---:|
| 8,388,608 | 16 | 174630147 | vqsort, prefetch 32 + streaming stores | 217.97 | 267.87 | 1.229× |
| 8,388,608 | 16 | 876321419 | vqsort, prefetch 64 | 217.68 | 267.40 | 1.228× |
| 1,048,576 | 16 | 174630147 | vqsort, prefetch 32 + streaming stores | 18.73 | 23.14 | 1.235× |
| 1,048,576 | 16 | 876321419 | x86-simd-sort, prefetch 32 | 19.41 | 24.65 | 1.270× |
| 8,388,608 | 64 | 174630147 | vqsort, prefetch 32 | 260.65 | 327.64 | 1.257× |
| 8,388,608 | 64 | 876321419 | vqsort, prefetch 32 + streaming stores | 269.22 | 384.55 | 1.428× |

The primary reference spent 72.39 and 71.66 ms in materialization. The grouped phase took 123.54 and 118.93 ms. Replacing gather with the contiguous copy medians (11.80 and 12.51 ms) in the timing estimate gives 157.37 and 158.53 ms, below the corresponding thresholds of 167.84 and 167.61 ms. Under that estimate, a real replacement would have only about 21–22 ms to materialize 128 MiB. The grouped phase includes constructing the schedule and scattering into the output window. No counters or subphase timings were collected to attribute the additional time.

## Reproduction

- [Source and commands](../../prototypes/agents/record-permutation/README.md), [raw timing samples](raw.csv).
- AMD Ryzen 7 5800X, Windows 11 build 26200, pinned logical CPU 8, one thread, 4 KiB system pages, GCC/MinGW-w64 16.1.0, `-O3 -march=native -DNDEBUG -std=c++20`. Installed RAM was previously reported as 31.89 GiB. Benchmark-owned RAM before reference-specific scratch was 480 MiB in the primary cell and 1,632 MiB in the 64-byte control, including the 96 MiB eviction buffer and verification output. All indirect methods allocate 64 MiB of packed keys in those cells, and grouping adds 264 KiB of scheduled requests and counters. These are explicit allocations. Peak process residency and internal scratch in the direct radix reference were not sampled.
- Highway `a3f6f68fcc368e5e3025ca25805eabda9d8a456f`, static vqsort AVX2. x86-simd-sort `6e059b14975df2e3c74260ec905167a1be5a34ca`, static AVX2. ska_sort header SHA-256 `440456435f9052998bd48fbc501870ce3975bcff400b906783768694f37264ca`, direct row sort with packed `(key, ordinal)` extractor. `memcpy` from the Windows UCRT through the MinGW build.
- IPS2Ra `83f6b76ca308b277b2acc3a36426a3baa3c9cb73` and IPS4o `08a5b926ee65cef19139057c6bde02bb5542c1cb` failed the Windows test build at `tbb/concurrent_queue.h`. WSL was unavailable to this session and there is no comparison against the Inoue–Taura merge sorter. The candidate already fails against available references. A passing candidate would require stronger reference coverage and real data.
- All 324 matrix calls, including 54 warm-ups, and all 36 smoke calls passed byte-exact verification. Timing phases are individually measured, so their medians need not add up to the median total. The small run count and within-cell variability limit conclusions about which of the closest references is fastest.

## Accounting

- Model: OpenAI GPT-6 (Codex session). The exact variant, token usage and per-run subscription cost were unavailable. No paid external compute was provisioned for this run.
