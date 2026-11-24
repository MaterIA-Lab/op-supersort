---
title: Compressing GPU-sorted keys for the trip back to RAM
date: 2026-11-24 12:24
verdict: failed
summary: The encoded return sent about half the bytes, and CPU reconstruction more than offset the transfer savings. Copying full keys won all six cases on the RTX 3070.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 11. Return GPU-sorted keys as narrow values and shared prefixes
result: 0.348-0.579× on four primary comparisons
baseline: Fastest verified median of one or four full-width copies and the three compressed controls after the same CUB sort
closes: [post-sort 16-bit return with host reconstruction under the measured GPU contract]
speedup: 0.348-0.579
how: After the GPU sorts the numbers, send the lower half of each number and a table of where the upper half changes. The CPU uses the table to rebuild each part of the array while the next part is in transit.
compared_with: The same GPU sort with a direct copy in one or four parts, compressed keys decoded after transfer, and 16-bit differences from a base key in each group.
faster_where: With 64 and 256 MiB of random 32-bit keys, transfer bytes fell about 50%. The full sort took 1.73-2.88 times as long as the best direct copy. Direct copying also won in both tests with keys concentrated in two ranges.
title_es: Comprimir en la GPU las claves ordenadas antes de devolverlas a la RAM
how_es: Después de ordenar los números en la GPU, se envía la mitad baja de cada número y una tabla que indica dónde cambia la mitad alta. La CPU reconstruye cada tramo mientras se transfiere el siguiente.
compared_with_es: La misma ordenación en GPU con una copia directa en uno o cuatro bloques, claves comprimidas que se reconstruyen al final y diferencias de 16 bits respecto a la primera clave de cada grupo.
faster_where_es: Con 64 y 256 MiB de claves aleatorias de 32 bits, se transfirió alrededor de un 50% menos de datos. La ordenación completa tardó entre 1,73 y 2,88 veces lo que tardó la mejor copia directa. La copia directa también ganó en las dos pruebas con claves concentradas en dos rangos.
---

# Compressing GPU-sorted keys for the trip back to RAM

**Decision. Close this return format for the tested configuration.**
It sent 49.61-49.90% fewer bytes from GPU to host, including the
prefix table. Total wall time was 1.73-2.88 times the fastest
reference on uniform keys. The candidate passed zero of four
primary cases, so the conditional holdout was skipped.
[Registered protocol](protocol.md) · [Prototype and reproduction](../../prototypes/agents/gpu-sort-return/README.md)

## Timings

Every method uploads the same full-width keys, uses the same CUB
radix sort, and returns a contiguous uint32 array to host RAM.
Wall time includes the upload, sorting, encoding, copying,
any CPU expansion, and synchronization. Each number is the
median of seven measured calls after two warm-ups. The ratio
divides the fastest reference median by the prefix overlap median.

| Input | Seed | Raw one, ms | Raw four, ms | Prefix serial, ms | Prefix overlap, ms | Frame serial, ms | Frame overlap, ms | Ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 MiB uniform | 59021 | 7.656 | 8.529 | 21.676 | 22.024 | 11.581 | 11.959 | 0.348× |
| 64 MiB uniform | 91457 | 7.567 | 7.345 | 20.905 | 20.695 | 10.914 | 11.722 | 0.355× |
| 256 MiB uniform | 59021 | 30.975 | 31.361 | 54.671 | 54.435 | 45.856 | 44.760 | 0.569× |
| 256 MiB uniform | 91457 | 30.847 | 31.999 | 56.666 | 53.303 | 45.121 | 46.693 | 0.579× |
| 64 MiB two clusters | 59021 | 7.799 | 8.483 | 12.608 | 11.227 | 11.251 | 11.171 | 0.695× |
| 64 MiB two clusters | 91457 | 7.971 | 8.067 | 12.805 | 12.302 | 12.387 | 11.631 | 0.648× |

The prefix method returned 32.25 MiB and 128.25 MiB, respectively.
Its four-tile CPU expansion took 14.7-14.9 ms at 64 MiB and 30.7-32.4 ms
at 256 MiB on uniform keys. Time spent waiting for DMA events is
excluded from those expansion diagnostics and charged to wall time.
With two occupied prefixes, expansion took 5.5-6.8 ms. The
fixed-block frame methods also lost to raw copying. They had no
overflow on uniform keys and resorted to one extra 16 MiB raw copy
after detecting the gap on each clustered input.

## Headroom for a faster decoder

For each primary input, take the winning raw method's median upload
plus sort time from CUDA events. Dividing the raw wall time by that
common cost gives a zero-return-cost estimate of 1.525-1.703×. Add
the serial prefix method's measured median encode-plus-return cost
and assume free CPU expansion. That yields 1.146-1.248×, below the
1.30× target on all four inputs. This phase-based estimate mixes
medians from separate methods on one device. It describes the
measured encoder and data layout. A decoder-only change has little
reason to advance under those costs.

## Verification and accounting

- All 252 measured calls and 72 warm-ups agreed exactly with a
  separate CPU sort. The benchmark filled the output with the
  complement of the oracle before each call outside the timer.
  Preflight exercised 27 fixtures with all six methods.
  [Verification](verification.txt) · [Raw samples](development.csv)
- Ryzen 7 5800X on Windows 11, logical CPU 8, one host thread, one
  CUDA stream and one RTX 3070. CUDA 12.1.105 built for sm_86 with
  CUB 2.0.1 and MSVC 19.34.31937. The benchmark reuses page-locked
  buffers and GPU workspace. The evidence covers synthetic input
  and this initialized GPU route. [Environment and digests](development-metadata.json)
- The common resources were two full-size pinned host buffers,
  two full-size device buffers, and 2.04 or 8.13 MiB of temporary
  CUB storage. The prefix variant requires another 32.25 or
  128.25 MiB on each side. The frame variant needs 32.50 or
  130.00 MiB on each side, including metadata. The harness shared the
  narrow-value buffers and reserved both sets of metadata.
- Model `gpt-6.2-sol`. External paid compute spend was zero.
  Model tokens, reasoning setting and session cost were not captured.

Run `python -X utf8 runs/2026-11-24-gpu-sort-return/analyze.py development`
from the repository root to check the digests, schedule and transfer
sizes, and recompute the timing comparisons and estimates.
