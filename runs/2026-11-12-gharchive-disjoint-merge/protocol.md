# GH Archive disjoint-batch timing protocol

- **Model** OpenAI GPT-6.1 Sol, Extra High, as identified by the owner. Local processing has no incremental cloud compute charges. Token count and billed model cost are unavailable in the session.
- **Question** How much does page remapping save when assembling an immutable, contiguous output from real hourly batch sizes that require no interleaving?

## Inputs and contract

Use all eight cases from the [coverage diagnostic](../2026-11-12-gharchive-page-coverage/README.md). Its independent merge found two slices per case, with the earlier batch entirely first. Reconstruct that exact source-side order and both row counts from the aggregate CSV. Generate unique rank keys and deterministic 128-byte records using payload seed 53. Real event timestamps determined the merge order and batch sizes. The timed fixture uses synthetic keys and payloads and keeps no per-event data. The algorithm compares keys, so this transformation preserves every ordering decision for the disjoint ranges. Verify the reconstructed coverage against the published aggregate for each case.

Use the previous candidate's single-threaded Linux/WSL2 contract. Inputs are already sorted, immutable, and page-aligned in a RAM-backed `memfd`. Each output is contiguous and read-only. Timed work includes assembly, output protection and the first sequential scan. Report teardown separately. Exclude archive fetch, decoding, sorting within a capture batch, payload preparation and input conversion, as for the existing candidate contract.

## Comparators and decision

- The unchanged remapping candidate uses the same 64 KiB minimum. Keep scalar, galloping bulk and hybrid fresh-output references and the already-touched hybrid reference from the synthetic experiment.
- Add a disjoint-range reference that checks the two endpoints and copies both runs with two `memcpy` calls. Run it with both fresh and already-touched output. This is the obvious strong reference for these cases. Report paired ratios against the fastest fresh-output reference and the fastest already-touched reference separately.
- Use one warm-up and five measured repetitions per method and case, rotating method order by case and repetition. Pin logical CPU 4 and touch the 64 MiB eviction buffer before each trial. Check every output byte and all mapped-byte and map-call counts. Publish raw samples, source commit, compiler, hardware, memory and timing bounds.

Report all eight cases and the counts reaching 1.3× and 1.5×. A gain here applies to assembly of disjoint ranges under the stated memory contract. The sample does not decide whether the mechanism helps on actual overlapping arrivals or establishes a new sorting result. Report any gain at or above 1.5× directly to the owner before broader exploration.
