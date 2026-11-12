# Results for disjoint GH Archive batches

The page-remapped output was **1.431–1.661×** faster than the best fresh-output reference for the six pairs where 48.25–51.46% of bytes could be mapped. It was **6.693–7.252×** faster for the two pairs where nearly all bytes could be mapped. All eight passed 1.3× and seven passed 1.5×. The comparison includes a reference that checks the endpoints and concatenates the runs with two `memcpy` calls.

With an already-touched destination available, remapping took about **2.0–2.6× as long** as the best reference in the six partial-mapping pairs (speedup 0.382–0.491×). It retained a **1.663–1.739×** gain in the two almost fully mappable pairs. In these pairs the first batch had a multiple of 32 records, so the start of the second batch also aligned in the output. The eight cases therefore expose a strong interaction between alignment and whether the output pages already exist.

The primary times include reserving and assembling the output, making it read-only, and a first sequential scan of one word per cache line. Measured teardown is reported separately. Adding teardown preserves the fresh-output result in all eight cases, with paired ratios ranging from 1.441× to 6.568×. The benchmark verified all **280 measured outputs and 56 warm-ups** byte for byte and checked that mapped bytes and extent counts exactly matched the published coverage.

The benchmark used one pinned logical CPU on a Ryzen 7 5800X under Ubuntu 22.04.3 and WSL2. The peak process RSS was 419,492 KiB, including source, output, verification and eviction buffers. It can count aliased backing pages through multiple addresses. [Machine and build metadata](metadata.txt)

The fixtures preserve the verified real batch sizes and source-side order and use synthetic keys and 128-byte payloads. All sampled time ranges were disjoint. The timed input was already sorted and in a `memfd`, with conversion and batch preparation outside the timing interval. This measures contiguous assembly of disjoint ranges. A claim about overlapping real arrivals, end-to-end ingestion, or novelty under the research goal needs further evidence. [Archive coverage diagnostic](../2026-11-12-gharchive-page-coverage/README.md) · [Research goal](../../GOAL.md)

The table reports paired speedups and median times generated from the [raw measurements](disjoint.csv).


| Batch pair | Records | Mapped | Fresh concat (ms) | Best fresh (ms) | Best resident (ms) | Remap (ms) | Remap teardown (ms) | Speedup vs fresh | Speedup vs resident |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-01-15 08 to 09 | 467,801 | 48.29% | 32.47 | 29.89 | 7.13 | 18.02 | 1.67 | 1.655× | 0.382× |
| 2025-01-15 09 to 10 | 480,271 | 100.00% | 32.69 | 29.61 | 7.09 | 4.03 | 0.75 | 7.252× | 1.739× |
| 2025-01-15 10 to 11 | 463,201 | 51.46% | 30.64 | 28.24 | 6.67 | 16.94 | 1.55 | 1.656× | 0.398× |
| 2025-01-15 08-09 to 10-11 | 931,002 | 50.24% | 61.81 | 57.52 | 14.56 | 34.64 | 3.11 | 1.661× | 0.415× |
| 2025-01-18 08 to 09 | 348,649 | 48.25% | 23.05 | 21.52 | 5.09 | 13.44 | 1.21 | 1.627× | 0.383× |
| 2025-01-18 09 to 10 | 352,321 | 51.21% | 30.65 | 29.00 | 10.00 | 20.33 | 1.22 | 1.431× | 0.491× |
| 2025-01-18 10 to 11 | 350,298 | 99.99% | 22.90 | 21.38 | 5.25 | 3.15 | 0.66 | 6.693× | 1.663× |
| 2025-01-18 08-09 to 10-11 | 698,947 | 49.88% | 47.40 | 43.63 | 10.42 | 26.57 | 2.42 | 1.640× | 0.392× |

- 8/8 cases reached 1.3× against the fastest fresh reference.
- 7/8 cases reached 1.5× against the fastest fresh reference.
- 2/8 cases reached 1.3× against the fastest resident reference.
- 2/8 cases reached 1.5× against the fastest resident reference.
