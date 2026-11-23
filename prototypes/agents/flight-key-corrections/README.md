# Flight key-correction replay

Author: agent:gpt-6.2-sol (Codex).

This single-threaded harness uses the frozen [direct span prototype](../key-correction-spans/README.md),
including its DeltaSort, unstable Rust sort and bulk extract-sort-merge
references. The additional stable Rust sort and interval-limited merge controls
exercise the same correction contract. The limited merges find a range that
contains the old positions and new insertion gaps before compacting that range.
They pay to find the range and translate the edit positions inside timing.
[Protocol and measured results](../../../runs/2026-11-23-flight-key-corrections/README.md)

## Reproduce

Use Python 3.10 or later and an x86-64 Rust toolchain with the Ryzen 5000 series
`znver3` target. The recorded build used Rust 1.96.0. Obtain
[OpenIntro's pinned `nycflights.rda`](https://raw.githubusercontent.com/openintrostat/openintro/b37b235dd702363d5ad87af68dff9533cc148160/data/nycflights.rda)
and [DeltaSort's pinned `lib.rs`](https://raw.githubusercontent.com/shudv/deltasort/89322c7bfb8d5b28b179650d08249398cbe0a977/src/lib.rs).
The runner verifies both source blobs. Run from the repository root, with a free
logical CPU and without other heavy workloads:

```powershell
python -X utf8 prototypes/agents/flight-key-corrections/run.py lab/nycflights.rda lab/deltasort/lib.rs lab/flight-replay lab/flight-results --cpu 8
python -X utf8 runs/2026-11-23-flight-key-corrections/analyze.py lab/flight-results
```

The runner builds the two Rust crates, converts the flight clocks to the
benchmark representation, and executes the four selected weeks sequentially.
The analysis verifies the recorded CSV digests and required trials before
reporting the results. To analyze the published samples, omit the directory
argument in the second command.
