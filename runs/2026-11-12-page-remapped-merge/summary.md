# Page-remapped merge pilot results

**Decision.** Continue to a measured candidate. For runs with a single overlapping edge, the estimated speedup was 1.52–1.59× across both sizes and both seeds. The estimate credits avoided copy cost using the separate 128 MiB calibration and assigns zero extra cost to mixed assembly.

At 4 KiB per extent, mapping and reading was 64 ms slower than copying and reading 128 MiB. At 64 KiB it saved about 48 ms. At 2 MiB and above it saved about 63 ms, including the first read. The mapping phase was cheap for large extents, while their first read took about 2.4–3.9 ms longer than reading the corresponding copied output. Baseline copy assembly includes fresh destination allocation and the cost of touching its pages.

The edge-overlap inputs contained about 75% full source pages, of which half aligned with the destination. Bursty inputs contained about 88% full source pages, of which only 2.7–6.9% of total bytes aligned with the destination. Thus, long source slices alone predicted poorly how many bytes would be reusable. The interleaved control had no reusable pages. The adjacent control's 21–26× estimates arise from subtracting almost all of the reference time and are particularly sensitive to small differences between calibration and merge timings. Treat them as a control for eligibility and measure their actual timings separately.

The experiment verified all 252 outputs, including 42 warm-ups, byte for byte. It ran on an AMD Ryzen 7 5800X in Ubuntu 22.04.3 under WSL2, pinned to logical CPU 4. Peak process RSS was about 323 MiB for calibration and 1,608 MiB for merge, including source, output, verification sequence and eviction buffer. See [machine and build metadata](metadata.txt).

The experiment uses generated layouts and a fresh, read-only output. It measures one word per cache line on the first sequential scan. Mapping assembly includes calls to install and protect the output. Verification and destruction of the output follow the timed interval. No hardware counters were collected. The next run measures actual end-to-end time with fresh seeds and checks sensitivity to an already-touched destination.


## Mapping versus copying 128 MiB

| Bytes per extent | Copy assembly (ms) | Map assembly (ms) | Copy scan (ms) | Map scan (ms) | Paired saving (ms) |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 91.42 | 128.92 | 10.82 | 42.77 | -64.28 |
| 65,536 | 58.07 | 6.63 | 6.42 | 10.35 | 47.85 |
| 2,097,152 | 65.67 | 0.25 | 6.47 | 9.16 | 62.84 |
| 16,777,216 | 65.52 | 0.05 | 6.28 | 9.02 | 62.64 |
| 134,217,728 | 66.41 | 0.02 | 6.67 | 8.98 | 63.59 |

## Merge coverage and optimistic speedup

| Records | Layout | Seed | Source pages | Mappable bytes | Mappable extents | Fastest reference (ms) | Estimated speedup |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1,048,576 | adjacent | 271 | 100.00% | 100.00% | 2 | 65.69 | 21.543× |
| 1,048,576 | adjacent | 1601 | 100.00% | 100.00% | 2 | 65.45 | 23.284× |
| 1,048,576 | edge_overlap | 271 | 75.00% | 37.50% | 1 | 63.90 | 1.581× |
| 1,048,576 | edge_overlap | 1601 | 75.00% | 37.50% | 1 | 68.50 | 1.522× |
| 1,048,576 | bursty | 271 | 87.63% | 2.74% | 1 | 60.33 | 1.029× |
| 1,048,576 | bursty | 1601 | 87.60% | 5.47% | 2 | 60.62 | 1.060× |
| 1,048,576 | interleaved | 271 | 0.00% | 0.00% | 0 | 60.54 | 1.000× |
| 1,048,576 | interleaved | 1601 | 0.00% | 0.00% | 0 | 60.81 | 1.000× |
| 4,194,304 | adjacent | 271 | 100.00% | 100.00% | 2 | 265.30 | 24.241× |
| 4,194,304 | adjacent | 1601 | 100.00% | 100.00% | 2 | 264.55 | 25.955× |
| 4,194,304 | edge_overlap | 271 | 75.00% | 37.50% | 1 | 258.71 | 1.584× |
| 4,194,304 | edge_overlap | 1601 | 75.00% | 37.50% | 1 | 257.51 | 1.588× |
| 4,194,304 | bursty | 271 | 87.60% | 6.85% | 10 | 240.02 | 1.077× |
| 4,194,304 | bursty | 1601 | 87.61% | 3.42% | 5 | 243.86 | 1.037× |
| 4,194,304 | interleaved | 271 | 0.00% | 0.00% | 0 | 247.57 | 1.000× |
| 4,194,304 | interleaved | 1601 | 0.00% | 0.00% | 0 | 246.25 | 1.000× |

Non-control cases clearing 1.3× on both seeds (2/4)
- 1,048,576 records, edge_overlap
- 4,194,304 records, edge_overlap
