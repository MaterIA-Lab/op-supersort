---
title: Bandwidth screen for three-byte sorting keys
date: 2026-11-15 15:16
verdict: diagnostic
summary: With eight workers, a transfer-only estimate including conversion reached 1.086–1.178×. All four primary cases missed the 1.30× gate before any sorting work was charged.
model: Codex (exact model and reasoning settings not captured)
cost: not captured
idea: 2. Compressed keys in flight for bandwidth-bound regimes
result: 1.086–1.178× estimated across four primary cases
baseline: fastest of memcpy and AVX2 streaming copy at full width
speedup: 1.086–1.178
estimate: true
closes: [24-bit width savings alone with up to two intervening memory transfers]
how: A bucket can remember the first byte of every key it contains. Store the other three bytes between passes and rebuild the full keys at the end.
compared_with: Measured sequential copies of four-byte and three-byte keys on the same cores. Used measured encoding and decoding times in the estimate.
faster_where: With eight cores, moving already packed keys was 1.166–1.331× as fast. Including both conversions and two intervening transfers brought the estimate to 1.086–1.178×. The experiment timed memory movement and conversion.
title_es: Prueba de ancho de banda con claves de tres bytes
how_es: Una cubeta puede recordar el primer byte de todas sus claves. Entre pasadas se guardan los otros tres bytes y al final se reconstruyen las claves completas.
compared_with_es: Se midieron copias secuenciales de claves de cuatro y tres bytes en los mismos núcleos. La estimación incluye los tiempos medidos de compresión y reconstrucción.
faster_where_es: Con ocho núcleos, copiar claves ya comprimidas fue entre 1,166 y 1,331 veces más rápido. Al sumar ambas conversiones y dos transferencias intermedias, la estimación quedó entre 1,086× y 1,178×. Se midieron transferencias y conversiones.
---

# Bandwidth screen for three-byte sorting keys

The width-only proposal missed the preregistered 1.30× gate in all four primary cases, including the 256 MiB arrays. Moving an already packed buffer was up to 1.331× as fast on eight cores. The estimate with encoding, decoding and two intervening copies was 1.086–1.178×. The best estimate across all worker counts was 1.237×. [Preregistered protocol](protocol.md) · [Raw samples](raw.csv) · [Analyzer](analyze.py) · [Environment and hashes](metadata.txt)

| Keys | Seed | Full-width copy (ms) | Packed copy (ms) | Pack + unpack (ms) | Estimated ratio with two interior copies |
|---:|---:|---:|---:|---:|---:|
| 16,777,216 | 104729 | 7.250 | 6.216 | 14.266 | 1.086× |
| 16,777,216 | 130363 | 7.440 | 5.955 | 13.503 | 1.171× |
| 67,108,864 | 104729 | 23.940 | 18.562 | 46.967 | 1.139× |
| 67,108,864 | 130363 | 24.652 | 18.515 | 46.686 | 1.178× |

The table uses eight pinned physical cores and sums per-phase medians across the seven measured rounds. The best median copy implementation is chosen independently at each width and for each case. One-core timings differed substantially between the two seed runs, despite the same byte counts. Frequency, background load and memory placement were uncontrolled. The conclusion uses the preregistered eight-core gate and makes no claim about the source of that variation.

The pure traffic model reaches `32/26 = 1.231×` with two interior transfers and first reaches 1.30× at eleven interior transfers. It assumes equal effective bandwidth and identical cache residency. This makes eliminating a full pass or changing which data fits in cache a different hypothesis with a different control. The measured screen covers reusable, sequential buffers. A complete radix sorter still owes a histogram, a scatter, allocation and a sorted output.

Verified 420 measured outputs, 60 warm-up outputs and eight separate boundary conversions byte for byte. Run the analyzer with `python -X utf8 runs/2026-11-15-compressed-key-bandwidth/analyze.py runs/2026-11-15-compressed-key-bandwidth/raw.csv`. The sixth and later fields preserve the method, time and verification result in every round. [Source and build instructions](../../prototypes/agents/compressed-key-bandwidth/README.md)
