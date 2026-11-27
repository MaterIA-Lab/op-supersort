# Rolling argsort with reusable packed ranks

The benchmark emits a contiguous row of absolute indices for each
stride-one window. Every method breaks key ties by original index.
The candidate sorts the union of up to 32 windows into a stable order
using packed `(key, index)` tags. Each union rank belongs to an
eight-position group. A membership mask describes which ranks belong
to the current window. On a slide, the masks for the outgoing and
incoming ranks change and the candidate repacks their groups. The
remaining groups keep their previously packed vectors.

The fixed-rank group cache is compared with stateless packing,
scalar enumeration of the same masks, fresh VQSort per window, and
incremental sorted arrays. The wide group stores use adjacent output
space within the buffer. The last row uses a small temporary row to
keep all writes within bounds. Streaming output makes the same
temporary row for every window.
[Protocol](../../../runs/2026-11-27-rolling-rank-chunks/protocol.md) · [Measured results](../../../runs/2026-11-27-rolling-rank-chunks/README.md)

## Reproduce

Use Windows with an AVX2 and CLFLUSHOPT capable CPU, GCC 16.1 and
Python 3.11 or later. Use the pinned Highway checkout from the
[record permutation setup](../record-permutation/README.md).
Choose an available logical CPU and a new work directory.

```powershell
python -X utf8 prototypes/agents/rolling-rank-chunks/run.py development lab/rolling-rank-chunks --highway lab/supersort-original/vendor/highway --cpu 8
python -X utf8 prototypes/agents/rolling-rank-chunks/run.py development runs/2026-11-27-rolling-rank-chunks/initial --report-only
python -X utf8 prototypes/agents/rolling-rank-chunks/run.py development runs/2026-11-27-rolling-rank-chunks/repeat --report-only
```

The runner verifies small fixtures before timing and compares all
window outputs with a separate stable reference after each call. It
writes the raw measurements and hashes of the sources, executable and samples.
