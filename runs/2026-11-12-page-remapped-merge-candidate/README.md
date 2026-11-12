# Page-remapped merge candidate — 2026-11-12

- **Model** OpenAI GPT-6.1 Sol, Extra High, as identified by the owner. Exact token count and billed model cost are unavailable in the session. Local WSL compute has no incremental cloud charges.
- **State** Protocol registered before candidate implementation and timing.

## Candidate and controls

Reuse the pilot's maximal-slice traversal. For each slice, map its maximal full-page interior into the reserved contiguous destination if the offsets are congruent and the interior contains at least 64 KiB. This is the smallest profitable extent band in the pilot. Copy any leading and trailing records and copy a slice in full if it is too short or misaligned. The output aliases immutable source pages and presents the same read-only contiguous interface as the references.

The primary comparison uses the fastest of three references for fresh output: the pilot's scalar and galloping bulk merges, and a hybrid that copies the non-overlapping prefix and suffix in bulk and merges the overlapping middle with a two-finger loop. Apply the same `mprotect` and first consumer scan for every method. Report a secondary comparison against the hybrid writing to a pre-touched destination. Reserve and fault that destination before timing for this control. It represents a caller with an already-resident buffer and a different memory contract. Its timing quantifies the sensitivity to first-touch cost.

## Workload and decision

Keep all pilot sizes and layouts, including adjacent and interleaved controls. Use **104729** and **130363** as fresh seeds. Run all five methods once as warm-up and five times for measurement, rotating order by repetition and seed. Pin one thread to logical CPU 4, evict 64 MiB before each trial, and verify every byte of every output after the first timed read. Report eligible bytes, bytes actually mapped and number of mapping calls. Record process peak RSS. Report teardown separately after verification and keep it outside the primary result interval, which ends when the first consumer scan completes.

For each case and seed, report the median across paired repetitions of `fastest fresh reference / candidate`. Treat a ratio of at least 1.3× on both seeds in a non-control layout as a measured synthetic result worth validating on real data. Also report the paired ratio versus the pre-touched reference for every case. Keep negative results and regressions. Practical importance, portability, and novelty relative to prior work require further evidence. If a measured synthetic case reaches 1.5× on both seeds, report it directly to the owner at this checkpoint before broader exploration.

## Reproduction

Use the same [Linux/WSL2 toolchain](../2026-11-12-page-remapped-merge/README.md#reproduction) as the pilot. The [experimental slice materializer](../../prototypes/agents/page-remapped-merge/slice.hpp) is used by the shared harness.

```sh
bash runs/2026-11-12-page-remapped-merge/run.sh lab/page-merge-candidate-smoke --candidate --smoke
bash runs/2026-11-12-page-remapped-merge/run.sh lab/page-merge-candidate --candidate
python3 runs/2026-11-12-page-remapped-merge/analyze.py lab/page-merge-candidate --candidate
```
