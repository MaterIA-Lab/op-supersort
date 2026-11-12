# Blocked record permutation probe — 2026-11-12

- **Author and model** `agent:gpt-6` (Codex session model family). Exact model variant, token count and billed model cost are unavailable to this session. No paid compute services are planned.
- **State** Protocol registered before candidate implementation and timing.

## Hypothesis and method

Once packed keys and source indices have been sorted, split final ranks into destination tiles of 256 KiB of payload each. Rewrite each tile's existing packed descriptors as `(source index, final rank)` and sort that tile by source index with vqsort. Visit its source rows in that order and write them directly to their final ranks. Each write lands inside one tile and each row is materialized once. The 256 KiB footprint leaves room for source lines and metadata in the target's 512 KiB L2. The critical question is whether locality repays the extra descriptor sort and the irregular destination stores.

Compare with both unchanged indirect references, pdqsort on whole rows, and both indirect references with straightforward software prefetch in the gather. Prefetch 32 rows ahead for the candidate and prefetch controls, touching both cache lines for a 128-byte record. Keep compiler flags, setup, affinity, eviction and correctness checks from the [headroom pilot](../2026-11-12-record-permutation/README.md). The candidate uses the same packed buffer as vqsort plus gather. Include all descriptor rewriting and reordering in the measured materialization phase and total.

## Workloads and decision

Repeat the entire eight-case matrix from the pilot with fresh SplitMix64 seeds **104729** and **130363** and the same one warm-up and three measured repetitions. Rotate all six methods across repetitions and seeds. Use a separate small development smoke input. Validate every timed output and warm-up with the existing verifier.

For each seed and case, take the median across the three paired ratios of `fastest measured reference / blocked candidate`. Continue with this mechanism only if at least one case reaches 1.3× on both fresh seeds. Record the ratios for all cases, even if a simpler prefetch control wins. A passing probe would still need comparison with a record-oriented SIMD sorter and IPS⁴o under equivalent resource and input/output conditions before a project finding could be claimed. A failed probe closes this exact tile-and-sort design.

## Reproduction

Use the same [pinned reference sources and GCC setup](../2026-11-12-record-permutation/README.md#reproduction) as the headroom pilot. The [experimental implementation](../../prototypes/agents/record-permutation/blocked.hpp) is built into the shared harness. The smoke mode checks both row widths with 5,003 records so each run crosses a tile boundary and exercises a partial last tile.

```sh
python runs/2026-11-12-record-permutation/run.py --vendor /path/to/vendor --output lab/blocked-smoke --cpu 4 --blocked-probe --smoke
python runs/2026-11-12-record-permutation/run.py --vendor /path/to/vendor --output lab/blocked-probe --cpu 4 --blocked-probe
python runs/2026-11-12-record-permutation/analyze.py lab/blocked-probe/raw.csv --blocked-probe
```
