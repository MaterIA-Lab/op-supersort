# Returning GPU-sorted uint32 keys to host memory

This probe returns a materialized array of sorted uint32 keys from a CUDA
sort. It compares a bulk transfer with two encodings of the sorted
output, each tested with serial and overlapped CPU expansion.
[Registered contract](../../../runs/2026-11-24-gpu-sort-return/protocol.md)

- **Upper-half runs.** A CUDA thread writes the lower 16 bits of each key.
  At a change in the upper 16 bits, that thread also records the position
  in a 65,536-entry table. The host fills consecutive output spans by
  combining their shared upper half with the transferred lower halves.
- **Frame of reference.** Every 128 sorted keys share the first key as a
  base. The device transfers 16-bit differences. If a difference
  overflows, the host requests the original keys for that quarter of
  the array and the timing charges both copies.
- **Raw output.** The same CUB sort returns full keys via one or four
  adjacent device-to-host copies.

In the overlapped versions, one nonblocking CUDA stream queues the side
table and four adjacent transfers. The host decodes a tile after its
event while the remaining copies can still proceed. Both encodings use
AVX2 with streaming stores and finish with a store fence.

## Reproduce

The registered build uses Windows, Python 3.11 or later, CUDA Toolkit 12.1,
MSVC 14.34, an AVX2 CPU and an Ampere GPU with compute capability 8.6.
Put `cl.exe`, `nvcc.exe` and `nvidia-smi.exe` on PATH. From the repository
root, use an unused output directory and choose an available logical CPU.
The registered run used logical CPU 8.

```powershell
python -X utf8 prototypes/agents/gpu-sort-return/run.py development lab/gpu-sort-return --cpu 8
python -X utf8 runs/2026-11-24-gpu-sort-return/analyze.py development --work lab/gpu-sort-return
```

The driver builds `bench.exe`, verifies edge cases, then runs warm-ups
and measured calls in shuffled method order for each input. Every call
checks the full output against a separate CPU sort. Allocate pinned input,
output and compression buffers and the GPU workspace before timing. The
timed interval runs from queueing the upload to completion of the final
transfer and any expansion. The driver records timings, transferred bytes,
compiler and device versions, and file digests beside the executable.

The analyzer can also read the recorded CSVs using Python alone.
[Measurements and decision](../../../runs/2026-11-24-gpu-sort-return/README.md)
