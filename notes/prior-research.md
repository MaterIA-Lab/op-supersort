---
author: agent:claude
---

# Prior local SuperSort research: lessons

Before joining OpenPrototypes, SuperSort was researched locally (experiments E001–E072). That work is **background, not an OpenPrototypes result**, and it does not constrain the current goal. Its authors, models and costs were not recorded and must not be invented.

The full archive (Spanish notes, source code, preregistrations, result summaries and CSV samples) was removed from `main` to keep the project focused. It remains in the git history: [prior-local at commit 195f578](https://github.com/MaterIA-Lab/op-supersort/tree/195f5781c0a1ddbd0fba53db0e47b7b3a18c3555/prior-local). Large files, binaries and most third-party `vendor/` snapshots were never imported. The original local laboratory is kept separately by the owner.

## Contract of that work

Ascending `uint32` keys without payload, one thread, allocation and final copy timed, exact check against `std::sort`. AMD Ryzen 7 5800X (AVX2, no AVX-512), Windows and later Ubuntu in WSL. References: vqsort (Highway), x86-simd-sort, IPS2Ra, pdqsort, ska_sort, `std::sort`. Its index reports 287,213 timing samples and 328,864 exact output checks, including warm-ups; these are not independent datasets.

## What it found

- **Low-entropy inputs win, high-entropy inputs do not.** In E054 (10M keys), a composite of range windows and an exact small-key dictionary was 1.5–2.7× faster than vqsort on narrow ranges (`dense16`), skewed, bimodal and few-distinct-key families. On uniform, wide-prefix and mixed inputs it was at parity (0.98–1.04×), and it lost on a dominant-key family. These wins come from detecting exploitable distributions that the references ignore, not from a new architectural mechanism.
- **Patching vqsort internals hit a wall.** E055–E072 replaced single phases (block partitioning, cycle partitioning, local radix finishers, packed 16-bit leaves, midpoint pivots). Every one failed its gate. The best (E071) saved about 4.4 ms of the roughly 9.4 ms needed on 10M uniform keys. This is the main reason the current goal demands new mechanisms rather than patches.
- **Small threshold changes are fragile.** `quick128` (an AVX2 network threshold change in x86-simd-sort) won on most uniform inputs but regressed on others, and a re-run without recompiling flipped a loss into a win. Run-to-run variation must be controlled before small effects are trusted.
- **Some reference timings look anomalous.** At 10M uniform keys the archive shows IPS2Ra at about 150 ms and its own LSD radix at about 100 ms, against about 47 ms for vqsort. Verify reference builds and allocation costs before relying on them.

## Viability review (2026-11-12)

The previous OpenPrototypes goal (≤75% of the best reference time in 90% of a large matrix of types, sizes, thread modes and object modalities) was judged very unlikely to be reachable, mainly because of the high-entropy wall above, memory-bandwidth limits at 10⁹ elements, and opaque comparators. The owner replaced it with an open search for genuinely new mechanisms; see [GOAL.md](../GOAL.md).
