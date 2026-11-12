# SuperSort: research goal

Can a general CPU sorting system exploit computer architecture to sort basic numeric types and objects by key substantially faster than the fastest applicable references on the project owner's machine?

The project builds on SuperSort research previously conducted locally. That work is background, not an OpenPrototypes result; preserve its provenance and limitations.

## Success criteria

Assess three sizes independently: **1,000**, **10,000,000**, and **1,000,000,000** elements. For each size at least 90% of predefined cases must meet the ambitious performance target. A useful partial result is possible without reaching this target: document where it works, its limitations, and all regressions. Assess single-threaded and multithreaded comparisons separately under equivalent resource conditions.

- A case is one combination of type and distribution, evaluated with multiple seeds. Define balanced distribution families in advance so similar cases cannot inflate the score.
- Treat records with numeric keys and associated payload, and generic objects sorted through a comparator, as separate modalities. Evaluate real workloads separately from the primary synthetic matrix.
- SuperSort must take at most **75% of the time** of the fastest applicable reference. This is a 25% time reduction, not a 1.25× speedup.
- Correctness is mandatory for every case, including the up to 10% missing the performance target. Object sorting preserves all objects and associated data; stability for equal keys is not required.
- Use competitive applicable references and equivalent resources. There is no preset memory cap; record memory use and account for relevant costs consistently.
- Document hardware, software, references, seeds, source, raw results, timing and limitations for reproducibility.
- Separately evaluate representative real-world workloads. Publish the full per-case results, regressions and memory use; no maximum regression threshold is imposed.

The intended usable deliverable is a reusable library with a simple interface and examples. Implementation language is open to experimentation, provided comparisons remain valid.

## Protocol to define before evaluation

Specify numeric types and object layouts, balanced distributions, seeds and independence, references, aggregation across seeds, repetitions and uncertainty, timing and allocation boundaries, resource rules, and treatment of NaNs, infinities and signed zeros. Mark cases exceeding machine capacity as not evaluable, publish the reason and never count them as passed. Calculate the percentage over evaluated cases and prominently disclose coverage and missing cases; do not present incomplete coverage as full achievement. The owner must review the protocol before it is frozen.

The existing E054 result used a different goal and narrower contract. It is historical evidence and does not establish success against this goal.
