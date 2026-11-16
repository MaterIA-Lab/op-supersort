# Linux test of producer-side placement

Registered 2026-11-16 before implementing the Linux backend and before measuring the candidate on Linux.

## Contract and inputs

Use the [three-output contract and generator](../2026-11-16-producer-page-placement/protocol.md) from the Windows experiment. A producer starts with two mutable sorted 128-byte-record buffers resident in RAM. It may reuse those buffers after the call. The result exposes both newly produced read-only batches and their stable merge as three contiguous ranges with a common lifetime. Read the merged view immediately.

- Primary holdout: two edge-overlap inputs at each of 128 and 256 MiB nominal merged size. The overlap is approximately 2%. Let `half` be half the nominal row count. For seed `1907348639`, use `half + 7` and `half + 11` rows. For seed `185028962`, use `half + 27` and `half - 4` rows. Both seeds and the lengths are new to the prototype.
- Reproduction controls: the previous two seeds `4316079` and `99237281` with their previous lengths at both edge-overlap sizes, plus their disjoint and interleaved cases at 128 MiB. Keep the same deterministic shuffle and duplicate policy. These eight cells provide a cross-check by shape. The Windows and Linux hardware differ.
- Run one warm-up and five measured rounds per case and method in shuffled order, on each of two independent standard Ubuntu 24.04 GitHub-hosted runners. Run jobs sequentially. Use one thread pinned to the highest permitted vCPU and ordinary 4 KiB pages. Use the recorded runner CPU and runtime versions. Use the existing untimed smoke cases before timing. Each trial starts after the same 96 MiB eviction sweep. Verify all three buffers byte for byte for every trial.

## Methods

The three direct references are the existing split copy plus bulk merge and the fused producer with cached or non-temporal stores. Use fresh anonymous pages on Linux. The three mapping methods are fixed input alignment, shifted inputs with lazy read-only aliases, and shifted inputs with eager population of read-only aliases using `MAP_POPULATE`. Keep batch storage and copied fragments in a new `memfd` for all three mapping methods. Output geometry, layout bounds and the verifier are shared with the Windows test.

Time fresh allocation and first touch, planning, creating both batches, stable merge or mapping, read-only protection, and the first consumer sweep of one word per cache line. Run verification afterward. Measure teardown separately. Report each phase, including the phase where population occurs, without subtracting it from the total. No background workloads are started by the runner during measurement.

## Decision

For each runner and cell, compare each mapping variant's median total with the fastest direct median. A single shifted variant must take at most 77% of the best direct time on **all four holdout cells on both runners**. Report the old-seed and disjoint/interleaved controls separately. A pass supports a larger test on a representative, nonvirtualized machine and on real inputs with the same production contract. A miss closes the tested Linux implementation for this fresh-output workload. Differences between this experiment and the previous Windows timings include the hardware, OS and standard library.

## Accounting

Codex via ChatGPT. Exact model variant, token count and marginal provider cost are unavailable. The repository is public and uses standard GitHub-hosted runners. No paid runner capacity was provisioned.

## Input-cache correction

The first runner of the initial workflow reported 480 MiB of L3 cache, larger than the inherited 96 MiB eviction sweep. That sweep alone did not establish that the source records were cold. Before comparing the initial timings, we registered a full rerun with the same shapes, seeds, references and decision rule. It retains the sweep and explicitly flushes the source cache lines before each timed call on x86-64 Linux. The fence completes the flush before the timer starts. Raw data from the inherited-sweep run remain available separately. The two runners with explicit input flushing determine the end-to-end verdict. [Intel optimization manual](https://cdrdv2-public.intel.com/814198/248966-Optimization-Reference-Manual-V1-049.pdf)
