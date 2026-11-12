---
author: agent:unknown
status: draft
---

# Proposed benchmark matrix — for owner review

This is a proposal, not a frozen protocol. All types are evaluated at 1,000, 10 million and 1 billion elements where feasible, separately for one thread and multiple threads. Mark unavailable cases explicitly and report the denominator and coverage.

## Numeric types

| Category | Proposed types | Why |
|---|---|---|
| Signed integers | int16, int32, int64 | Common narrow, standard and wide keys; include negatives and extremes. |
| Unsigned integers | uint16, uint32, uint64 | Common representations; include zero and maximum values. |
| Floating point | float32, float64 | Common numeric formats; define NaNs, infinities and signed zeros before measuring. |
| Optional later | int8, uint8, other formats | Useful in some workloads; defer to avoid silently widening initial scope. |

## Objects

1. Key-value records: numeric keys with payloads of multiple fixed sizes; check every key/payload association and duplicate.
2. Generic objects: representative objects with an explicit comparator; ensure candidate and reference use identical order semantics and comparator costs.

Specific key types, payload sizes and object representations remain to be agreed. Stability is not required. Both modalities are separately reported so a narrow key-only result is not portrayed as general object support.

## Distribution families

Propose uniform, skewed, low-cardinality/duplicates, already sorted and reverse sorted, nearly sorted, runs, and mixed/adversarial structures. Define exact generators and balancing before freezing the matrix. Evaluate multiple independent seeds where meaningful; seeds of deterministic patterns are not independent cases.

## Comparisons and reporting

Choose applicable leading implementations per type, interface and thread mode, with the same semantic contract. Use the fastest applicable reference per case; document versions and compile settings. Preregister repetitions, paired ordering, seed aggregation, uncertainty and which costs are included. Report the case matrix, pass ratio among evaluated cases, missing cases, per-family results, time ratios, regressions, memory and hardware. Assess real-world workloads separately from the primary matrix.
