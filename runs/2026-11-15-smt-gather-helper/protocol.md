---
author: agent:codex
---

# Preregistered helper-thread screen for record gathers

A helper can issue indirect loads while a worker copies records in their final order. The opportunity is to hide the wait for scattered reads. The cost is using a hardware thread that could move half the records itself. This experiment fixes the destination order and measures just the materialization stage of an indirect sort.

## Inputs and placement

- Primary: `2^21` distinct 128-byte records, 256 MiB per array, immutable input and a reusable aligned destination. Fisher–Yates permutations driven by SplitMix64, seeds 104729 and 130363, model uniformly distributed source addresses. The two workers are pinned to two hardware threads of the same physical core. Select the first physical core with both siblings available from Windows topology.
- Controls: same problem and seeds on one hardware thread each on two physical cores. Also repeat on the sibling pair with `2^15` records to expose costs when the working set fits in the shared last-level cache.
- Generate data and start persistent threads outside the clock. Poison the destination before each trial. Sweep 128 MiB to evict shared cache before each primary and two-core trial. Use an 8 MiB sweep on the small control and explicitly warm its source and order before timing. Time start and completion barriers and any non-temporal store fence. Verify every byte outside the timer against the specified permutation. One warm-up and seven measured rounds. Rotate and reverse the method order by round and seed.

## Arms

- Two workers, each producing half the destination. Try cached stores with no prefetch and with 16, 32, 64 and 128 records of in-thread lookahead. Also use non-temporal stores with zero and 32 lookahead. Prefetch both source cache lines per record.
- One worker copies all rows with built-in 32-record lookahead and cached stores while the other is idle. This is a diagnostic of the value of the second thread.
- One worker copies all rows and publishes progress every 128 records. A helper reads at least one chunk ahead and no farther than 256 or 1,024 records past the last published boundary. Run pairs using a prefetch instruction or a demand read of the first byte of each source cache line. Use cached stores for these four arms, plus an arm using non-temporal stores and a 1,024-row prefetch helper. Record the fraction of rows for which the helper issued requests. This count does not tell whether the lines were still cached when the consumer used them.

## Decision rule

For each case the baseline is the fastest median of all seven split gathers on the same CPU placement. Advance a helper design only if the same helper arm reaches at least 1.30 on both fresh primary seeds. Report every case, including results against the single-worker diagnostic. The test measures permutation and omits key sorting, allocation and a subsequent consumer scan. A positive result would require an end-to-end test using real layouts.
