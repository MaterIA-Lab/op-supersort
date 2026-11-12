# Blocked record permutation results

The candidate missed the 1.3× threshold on both fresh seeds in all eight cases. Its paired median end-to-end speedup ranged from 0.542× to 0.648×, equivalent to taking about 54–85% more time than the fastest measured reference. Close the tile-and-sort design under the preregistered decision rule.

The combined materialization phase, including descriptor rewriting, descriptor sorting and payload copying, took 1.67–2.14× as long as the original vqsort gather by paired median. This combined cost erased the potential gain estimated by the [headroom pilot](../2026-11-12-record-permutation/summary.md). The phase timing does not isolate descriptor sorting from the costs of reading source rows and writing out-of-order within destination tiles. Cache and TLB events were not measured.

One of the two prefetch controls was fastest in all 48 measured paired repetitions. Its paired median speedup over the fastest non-prefetch reference was 1.051–1.235× across the sixteen case-seed combinations. This makes prefetch a stronger control for the tested workloads. The probe used one fixed prefetch distance and one tile size.

All 288 measured outputs and 96 warm-ups passed complete verification on the AMD Ryzen 7 5800X, Windows 11, GCC 16.1.0, with one thread on logical CPU 4. Peak process working set was 1,179,598,848 bytes (about 1,125 MiB). The candidate reused the 32 MiB packed index at the largest size. The run covered synthetic keys on one CPU and excluded IPS⁴o and the record-oriented SIMD merge from its reference set. The negative comparison already holds against the references that were measured.

Times below are medians in milliseconds. The speedup column is the median of paired end-to-end ratios. Generate this table with `analyze.py --blocked-probe` and the [raw samples](raw.csv).


| Records | Bytes per row | Keys | Seed | vq + gather | x86 + gather | pdqsort rows | vq + prefetch | x86 + prefetch | Blocked | Blocked materialization | Blocked speedup |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,048,576 | 64 | uniform32 | 104729 | 33.28 | 32.29 | 68.82 | 29.86 | 31.02 | 53.49 | 37.82 | 0.556× |
| 1,048,576 | 64 | uniform32 | 130363 | 30.75 | 30.20 | 66.25 | 28.40 | 28.95 | 49.48 | 36.03 | 0.573× |
| 1,048,576 | 64 | low12 | 104729 | 32.96 | 32.65 | 50.21 | 30.33 | 30.36 | 51.97 | 37.27 | 0.582× |
| 1,048,576 | 64 | low12 | 130363 | 31.01 | 30.12 | 46.87 | 28.29 | 28.83 | 48.39 | 34.67 | 0.585× |
| 1,048,576 | 128 | uniform32 | 104729 | 47.07 | 47.22 | 97.83 | 42.71 | 42.73 | 78.59 | 63.39 | 0.542× |
| 1,048,576 | 128 | uniform32 | 130363 | 48.35 | 46.36 | 97.89 | 43.03 | 42.85 | 78.09 | 63.27 | 0.547× |
| 1,048,576 | 128 | low12 | 104729 | 46.64 | 46.17 | 79.26 | 42.89 | 43.13 | 74.00 | 59.15 | 0.580× |
| 1,048,576 | 128 | low12 | 130363 | 51.38 | 46.13 | 75.59 | 44.53 | 43.68 | 74.17 | 59.21 | 0.587× |
| 4,194,304 | 64 | uniform32 | 104729 | 141.57 | 136.97 | 322.64 | 125.28 | 125.52 | 215.99 | 152.68 | 0.585× |
| 4,194,304 | 64 | uniform32 | 130363 | 129.34 | 134.10 | 301.91 | 120.27 | 120.95 | 203.67 | 144.98 | 0.601× |
| 4,194,304 | 64 | low12 | 104729 | 130.00 | 126.72 | 204.60 | 120.76 | 122.35 | 198.55 | 139.04 | 0.608× |
| 4,194,304 | 64 | low12 | 130363 | 126.96 | 127.25 | 204.57 | 120.50 | 120.58 | 195.95 | 136.06 | 0.614× |
| 4,194,304 | 128 | uniform32 | 104729 | 200.57 | 202.24 | 486.73 | 184.27 | 184.96 | 319.53 | 251.01 | 0.576× |
| 4,194,304 | 128 | uniform32 | 130363 | 244.12 | 241.56 | 529.22 | 195.67 | 195.66 | 358.36 | 284.25 | 0.546× |
| 4,194,304 | 128 | low12 | 104729 | 213.28 | 219.33 | 454.89 | 216.84 | 201.96 | 343.15 | 253.82 | 0.604× |
| 4,194,304 | 128 | low12 | 130363 | 195.60 | 196.33 | 380.37 | 185.18 | 185.81 | 285.14 | 215.55 | 0.648× |

Cases reaching the candidate threshold on both fresh seeds (0/8)
