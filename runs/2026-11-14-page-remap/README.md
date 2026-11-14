---
title: Windows page remapping and first read
date: 2026-11-14 15:45
verdict: failed
summary: For 64 KiB blocks, Windows remapping and a first read took 2.21–2.54× the time of streaming copy and a first read. The first access to the new virtual addresses dominated even when larger blocks made the remap calls fast.
model: agent:gpt-6 (Codex)
idea: 1. Virtual memory as a data-movement engine
result: 0.394–0.453× across two primary seeds
baseline: AVX2 streaming copy plus first sweep into a reused output
closes: [Windows placeholder remapping for the measured contract]
cost: not captured
---

# Windows page remapping

Registered 2026-11-14 before implementing or timing the microbenchmark.

This is a Windows counterpart to the earlier [Linux remapping pilot](../2026-11-12-page-remapped-merge/summary.md), using a resident copy destination and reading one word per page. The measurements do not reverse results obtained with the other platform and output contract.

## Workload and threshold

- Reassemble 256 MiB of existing immutable contiguous runs into another contiguous read-only range, on one thread on logical CPU 8. A caller can release its source mapping once the result is ready. The primitive knows the order of runs for all methods. The source is a pagefile-backed section and is touched before timing. The primary extent size is 64 KiB. Controls use 4 KiB and 2 MiB extents within the same number of bytes, with ordinary 4 KiB pages.
- Use the same independently shuffled extent order for each method, with fixed seeds `40577317` and `971334011`. Smoke inputs use 4 MiB with seed `523` at all three sizes. Every extent is eligible for remapping. This is a favorable model of the assembly step for disjoint sorted ranges.
- Compare fresh placeholder reservation, splitting and page mapping with an ordinary per-extent `memcpy` and an AVX2 per-extent non-temporal copy into a reused precommitted buffer. Pin the thread, evict approximately 96 MiB before each call, and shuffle method order within one verified warm-up and five measured rounds per seed and size. Time assembly, a first sweep visiting one word per 4 KiB page, and release of any per-call output views. Check the sweep against the expected sequence and every byte of the output against the mapped source extent before release.
- The 64 KiB remap must take at most 77% of the time of the faster copy, using the median of assembly plus first sweep in both primary seeds. Report whether teardown preserves any gain. A pass would only establish headroom under this model. Before treating any future result as a sorting finding, measure eligibility and sorting end to end on actual workloads, with the same output contract for all references.

## Result

**Rejected for this Windows implementation.** With 64 KiB extents, the read-only remap plus first sweep took 95.21–111.75 ms versus 43.13–44.07 ms for streaming copy plus sweep, or 2.21–2.54× the time across two seeds.

| Extent | Seed | Remap assembly, ms | Remap first sweep, ms | Remap with sweep, ms | Streaming copy with sweep, ms | Remap with sweep and release, ms |
|---:|---:|---:|---:|---:|---:|---:|
| 64 KiB | 40577317 | 22.33 | 72.87 | 95.21 | 43.13 | 125.40 |
| 64 KiB | 971334011 | 24.27 | 85.45 | 111.75 | 44.07 | 149.43 |
| 4 KiB | 40577317 | 341.71 | 100.37 | 445.26 | 39.37 | 691.81 |
| 4 KiB | 971334011 | 397.95 | 110.22 | 510.17 | 44.35 | 724.17 |
| 2 MiB | 40577317 | 0.64 | 83.03 | 83.60 | 29.62 | 96.68 |
| 2 MiB | 971334011 | 0.67 | 83.28 | 83.88 | 57.35 | 101.12 |

Each column is the median of five measurements of that phase or sum of phases. Streaming AVX2 copy beat the ordinary `memcpy` reference in all six cells. With 2 MiB extents, 128 views let assembly finish in under 0.7 ms, but the sweep through the new virtual addresses alone took about 83 ms. This is consistent with first-access costs for populating the new mappings. No fault counters were collected. Teardown was timed after untimed bytewise verification, so it follows a full read of the output. The source mapping and its lifetime costs were common to all methods.

## Reproduction

- [Source and commands](../../prototypes/agents/page-remap/README.md), [raw timing samples](raw.csv).
- AMD Ryzen 7 5800X, Windows 11 build 26200, logical CPU 8, one thread, 4 KiB pages, GCC/MinGW-w64 16.1.0. Remap used `VirtualAlloc2`, `VirtualFree`, `MapViewOfFile3` and `UnmapViewOfFileEx` from this Windows build. The `memcpy` reference uses the Windows UCRT. The streaming reference uses AVX2 32-byte non-temporal stores with a fence before consumption.
- The process reserves 256 MiB for the source section, 256 MiB for the reusable copy destination, and 96 MiB for cache eviction, plus up to 512 KiB of extent offsets. Remapping adds 256 MiB of virtual address space backed by the original section. Kernel memory overhead and peak residency were not sampled.
- All 108 matrix calls, including 18 warm-ups, and nine smoke calls passed bytewise verification. The result applies to a synthetic all-aligned workload on this Windows API path. Linux and real sorted-run eligibility were outside this test.

## Accounting

- Model: OpenAI GPT-6 (Codex session). The exact variant, token usage and per-run subscription cost were unavailable. No paid external compute was provisioned for this run.
