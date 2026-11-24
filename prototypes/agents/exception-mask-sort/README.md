# Stable sort with masks for nearby equal keys

The input contains immutable 64-byte records and a parallel uint32
key column. The output contains complete records with ties in source
order. The prototype holds up to 64 nearby records with one common
key in a single sortable tag. A mask gives their source positions.
Different keys in the same block receive ordinary row tags.
[Registered contract](../../../runs/2026-11-24-exception-mask-sort/protocol.md)

For every block, the mask encoder chooses a key from the first, middle
and last positions. AVX2 equality identifies the matching positions.
A group tag uses the block start as its tie-break position and cannot
share a key with any exception in that block. Equal-key tags from
different blocks and equal-key exceptions within a block therefore
retain the original order. Expanding a group visits its positions
left to right.

References tag every row or use AVX2 to detect contiguous equal-key
runs. All encodings are timed with the same VQSort and stable byte
radix controls. The output writer coalesces consecutive source
positions, prefetches 24 tags ahead and writes complete cache lines
with streaming stores. Only tags and their metadata enter the sort.

## Reproduce

Use Windows, Python 3.11 or later, GCC 16.1.0 and an AVX2-capable
Zen 3 CPU. Use the pinned Highway commit from the
[record permutation setup](../record-permutation/README.md).
From the repository root, provide an unused work directory and a
logical CPU available to the process. The experiment used CPU 8.

```powershell
python -X utf8 prototypes/agents/exception-mask-sort/run.py development lab/supersort-original/vendor/highway lab/exception-mask-sort --cpu 8
python -X utf8 runs/2026-11-24-exception-mask-sort/analyze.py development --work lab/exception-mask-sort
```

The runner builds the executable, checks its output on small and
adversarial fixtures and verifies all records in the timed inputs.
Allocation and release of sort scratch are timed. The analyzer
checks the source and sample digests and recomputes the decision.
[Results and geometry audit](../../../runs/2026-11-24-exception-mask-sort/README.md)
