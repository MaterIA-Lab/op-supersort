# Stable record merge by short-window ranks

The inputs are ordered 64-byte records with their dense uint32 key
columns already present. The output is a separate contiguous record
array. A left record precedes a right record with the same key.
[Registered contract](../../../runs/2026-11-24-rank-window-merge/protocol.md)

In each pass, compare the eighth unconsumed key from each input.
If the left key comes first, the next output window consists of all
eight left records and the right records with keys strictly below
that endpoint. If the right key comes first, the window contains all
eight right records and the left records with keys at most that
endpoint. In both cases the opposing input contributes at most seven.
The uninspected suffixes can therefore wait until later windows.

The position of each record from the selected block is its position
in that block plus the number of opposing keys that precede it. AVX2
compares each selected key to the opposing eight keys in one operation.
Population counts give those ranks and a small mask stores the occupied
slots. The merge writes the records from each input in turn, then
continues from the first unconsumed record on each side. Both cached
and streaming stores are tested, with a direct merge for the tail.

## Reproduce

Use Windows, Python 3.11 or later and GCC 16.1 on a Zen 3 CPU with AVX2
and CLFLUSHOPT. Put `g++` on PATH and use an empty or unused work
directory. The registered affinity was logical CPU 8.

```powershell
python -X utf8 prototypes/agents/rank-window-merge/run.py development lab/rank-window-merge --cpu 8
python -X utf8 runs/2026-11-24-rank-window-merge/analyze.py development --work lab/rank-window-merge
```

The runner builds the executable, checks edge fixtures and measures
the full stable merge for each method. It poisons the output before
each call, flushes input, output and replay plan from cache, and
verifies every output byte outside the timer. Only the diagnostic
replay reads a precomputed per-window schedule. The recorded CSVs
can be analyzed independently of the executable.
[Measurements and decision](../../../runs/2026-11-24-rank-window-merge/README.md)
