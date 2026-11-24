# Varying-bit tags for stable 128-bit argsort

Given immutable two-word keys, return the stable permutation as contiguous
uint32 indices. The prototype keeps as many of the most significant varying
bits as fit in a 64-bit tag with the row index. Within a tied tag prefix the
comparison falls back to both original key words and the original index.
[Protocol and measurements](../../../runs/2026-11-24-varying-bit-argsort/README.md)

Dropping a bit that is identical throughout the input preserves every
lexicographic comparison. Dropping a suffix of the remaining bit sequence
preserves comparisons between different abbreviated prefixes. The complete
comparison restores order inside each tied prefix. Exact ties preserve
input order because the original index is the final tie-break.

## Reproduce

Use an AVX2 and BMI2 capable x86-64 host and GCC 16.1.0. Prepare Highway
and pdqsort using the pinned sources in the
[record permutation build instructions](../record-permutation/README.md).
The runner checks the Highway commit, checks that its tracked source matches
the commit and checks the exact pdqsort blob. Use a scratch directory and
an available logical CPU.

```powershell
python -X utf8 prototypes/agents/varying-bit-argsort/run.py development lab/supersort-original/vendor lab/varying-bit-replay --cpu 8
python -X utf8 runs/2026-11-24-varying-bit-argsort/analyze.py development lab/varying-bit-replay
```

The runner verifies small and adversarial inputs before timing. It times
the full call, including allocation and releasing scratch, and checks every
output index after each call. Omit the directory for the analyzer to read
the published measurements.
