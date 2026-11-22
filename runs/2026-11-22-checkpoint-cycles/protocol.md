# Sparse saved-row cycle cuts: preregistered kill test

Author: agent:gpt-6 (Codex). Registered 2026-11-22 before implementation or timing.

## Hypothesis

Sort compact key/index tags and use up to 64 saved original rows to split the
final in-place permutation into independent paths. A path terminates at ANY
saved position and reads that position from its saved copy. Interleave these
paths, prefetch their next source rows, mark processed tags, and then apply
ordinary cycle rotation to all remaining cycles. This may remove the extra
payload buffer and copy-back pass while overcoming a single dependent walk.

Cycle rotation is known. The proposed difference is cutting arbitrary cycles
at cheap regular saved positions without first discovering cycle structure.
The closest primary sources are recorded in idea 8 of `notes/ideas.md`.
Novelty is not established, and a speedup alone cannot establish it.

## Contract and inputs

- Sort an ordinary mutable array of trivially copyable, 128-byte rows in place,
  stable ascending by unsigned 32-bit key. A unique input ordinal plus fifteen
  uint64 payload words identify each row. Results must end at the same base
  address. No promise about distribution is supplied to any sorting routine.
- Caller-provided reusable scratch is available: N uint64 tags and N 128-byte
  rows. Every method may use it; the candidate uses the tags and at most 64
  saved rows. Allocation and first touch of that caller-owned workspace are
  outside this screen for every method. A positive result needs fresh-allocation
  and stronger-library checks before any general performance claim.
- Primary: N=1,048,576 (128 MiB), independent uniform32 keys and seeds 48071,
  65827. These are development kill-test inputs, not holdouts.
- Controls: N=8,192 with uniform32 keys (resident), and N=1,048,576 with eight
  equiprobable keys; both registered seeds. These do not replace the primary.
- Fix the checkpoint budget at 64 before timing. For any N, choose a
  power-of-two stride at least ceil(N/64) and use all multiples below N.
  Checkpoint count is therefore at most 64. The algorithm must handle arbitrary
  lengths, not just powers of two, and must not recognize a workload pattern.

## References

1. Highway vqsort tags followed by ordinary marked cycle rotation, with a
   one-step-ahead software prefetch of each source row.
2. Highway tags followed by a cached gather with prefetch 32 rows ahead and
   memcpy back into the caller's original array.
3. Highway tags followed by an AVX2 non-temporal gather with the same prefetch
   and a sequential AVX2 streaming copy-back. Fence all streaming stores.
4. x86-simd-sort tags followed by the same streaming gather and copy-back.
5. pdqsort directly on whole rows, using `(key, input_ordinal)` comparison for
   the same stable order. Use the existing archived header without changes.

Pin Highway a3f6f68fcc368e5e3025ca25805eabda9d8a456f and x86-simd-sort
6e059b14975df2e3c74260ec905167a1be5a34ca; record the pdqsort header hash.
The direct gather controls must be present: beating only a serial cycle walker
is not enough. IPS4o and record-oriented SIMD merge remain necessary references
for a confirmed finding; their unavailable Windows builds are not an excuse
to declare a positive screen a completed finding.

## Measurement and correctness

- One thread pinned to logical CPU 8 on the Ryzen 7 5800X, GCC 16.1, native
  Zen 3/AVX2 optimization. No heavy concurrent local workload.
- Before each call reset the working array outside timing. For large cases
  CLFLUSH the working rows and both reusable scratch buffers and fence before
  timing. Resident controls omit flushing.
- Include tag extraction, sorting, saved-row copies, mark writes, fallback
  scanning, full payload permutation and copy-back where applicable. Record
  key/index sorting and materialization phases as well as the whole call.
- One warm-up plus five measured rounds; deterministically shuffle method
  order within rounds. Keep all raw samples and method names.
- Verify every output row byte for byte against the original input addressed
  by an independent `std::sort` of original row ordinals by key and ordinal.
- Before timing test empty arrays, arbitrary lengths, identity, reversal,
  one long cycle, cycles with several checkpoints, cycles with no checkpoints,
  three-cycles and random permutations. Exhaustively test all permutations
  through length eight. Failure blocks timing.

## Gate and next step

Kill the implementation if it takes more than 77% of the fastest reference's
median on either primary seed. Do not tune checkpoint count or select a new
primary distribution after seeing the results. If both pass, preserve this
version, audit novelty further and validate fresh seeds 32452843 and 49979687
at 1,048,576 and 2,097,152 rows with stronger references and allocation charged.
Report any measured >=1.5x result provisionally to the owner before broad
exploration; confirmation still requires the missing controls and novelty audit.

## Accounting

GPT-6 (Codex); exact deployment variant and reasoning settings unavailable.
Tokens and session cost are not captured. The screen uses local compute only.
