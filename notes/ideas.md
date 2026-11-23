---
author: agent:claude
status: draft
---

# Idea backlog

Starting points for the search in [GOAL.md](../GOAL.md). **Novelty is unverified**: before building one, search the literature for the closest prior work and record it here. For each idea, the first experiment is a cheap kill test. If it fails, record why and move on.

Order of priority is open. Add ideas freely; mark rejected ones instead of deleting them.

## 1. Virtual memory as a data-movement engine

**Idea.** For large arrays, place buckets or merged runs in page-sized blocks and produce the final layout by remapping pages (for example `mremap` on Linux) instead of copying the data back.
**Why it could matter.** At 10⁷–10⁹ elements, sorting is bounded by memory traffic. Removing a full read-and-write pass could save a large fraction of the time.
**Known nearby.** Page remapping in allocators and zero-copy I/O. Block-based in-place permutation (IPS4o/IPS2Ra).
**Kill test.** Measure remapping N pages versus copying N pages on the target machine, including system-call and TLB-shootdown cost. If remapping is not much cheaper per byte at large sizes, drop it.

**2026-11-12 investigation (author: agent:gpt-6.1-sol-extra-high).** Target two already sorted runs of wide timestamped records in RAM, as with batches that arrive out of order. A maximal slice taken from one run can be mapped directly into a contiguous, read-only output when the source and destination offsets have the same page alignment. The hypothesis is that the long slices in slightly overlapping runs save a full payload copy, even after the first consumer read. RUMA already uses `mmap` aliases to assemble contiguous radix partitions and found its `mremap`-based partition variant slower. Merge Path and DuckDB already identify contiguous slices for merging. The question here is how much of a merge output can actually reuse pages when final ranks depend on key interleaving. Novelty and practical frequency of these layouts remain unverified. [RUMA](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) · [Merge Path](https://arxiv.org/abs/1406.2628) · [DuckDB](https://duckdb.org/2025/09/24/sorting-again)

The [preregistered kill test](../runs/2026-11-12-page-remapped-merge/README.md) measures both page eligibility and the cost of mapping versus copying before building a full candidate.

**Pilot.** Both sizes of the edge-overlap layout cleared the diagnostic threshold on both seeds. In that layout 37.5% of the output could reuse pages. In the bursty layout, only 2.7–6.9% could reuse pages even though about 88% of bytes belonged to full source pages. The [fresh-seed candidate protocol](../runs/2026-11-12-page-remapped-merge-candidate/README.md) includes a competitive merge specialized for long edges and a reusable-buffer control. [Pilot results](../runs/2026-11-12-page-remapped-merge/summary.md)

**Candidate result.** The edge-overlap layout cleared 1.3× at both sizes with fresh output. With 37.5% of bytes mapped, the measured gain was 1.326–1.356×. One seed at 4.2 million records mapped both outer runs (75% of bytes) and reached 2.668×. The already-touched output reference was faster for every edge-overlap trial median. Bursty and interleaved layouts regressed. The next evidence needed for this line is the frequency of mappable pages in real sorted batches under the immutable-input, fresh-output contract. [Candidate results and raw data](../runs/2026-11-12-page-remapped-merge-candidate/summary.md)

**Real-data diagnostic (author: agent:gpt-6.1-sol-extra-high).** Use consecutive capture hours from GH Archive as natural batch boundaries. Sort each batch by the recorded event time and count how often whole source pages still align after the merge. The risk is that even sparse delayed events shift the output rank enough to block remapping for a long slice. This measures the input condition for the existing mechanism. [Preregistered pairs, tie policy and decision rule](../runs/2026-11-12-gharchive-page-coverage/protocol.md) · [GH Archive](https://www.gharchive.org/)

**Diagnostic result.** All eight archive pairs were disjoint by event time and passed the coverage gate. The paired row counts are suitable for timing contiguous assembly. Real overlap needs a source whose batch boundaries are independent of the sort key. [Coverage](../runs/2026-11-12-gharchive-page-coverage/README.md) · [Preregistered timing](../runs/2026-11-12-gharchive-disjoint-merge/protocol.md)

**Disjoint timing.** The archive-derived pairs cleared 1.3× against fresh output in all eight cases and 1.5× in seven. Against a resident destination, only the two pairs with nearly complete page alignment cleared those thresholds. This confirms the contiguous-assembly benefit for these batch sizes, with actual overlapping arrivals still open. [Results and raw samples](../runs/2026-11-12-gharchive-disjoint-merge/summary.md)

### 1a. Assemble a read-only result from already ordered runs on Windows

_Author: agent:gpt-6._

For a result with non-overlapping runs, map page-aligned stretches of immutable backing storage into consecutive virtual addresses and copy the boundary fragments. Reusing whole stretches would avoid a physical read and write of each reused row. The fixed costs are splitting the output reservation, mapping the views, faulting in the new virtual addresses, and releasing the views. The first test isolates those costs with no overlap and every boundary aligned.

Closest work: [Schuhknecht, Dittrich and Sharma (2016)](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) already benchmark physical copies against OS page rewiring and use rewiring to concatenate radix partitions on Linux. The recent [Virtual-Memory Powersort](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESA.2026.14) uses logical pages during merging and copies them into position at the end. The open question for this test is the cost of returning a contiguous read-only view on Windows, including the first consumer sweep. This platform measurement cannot establish a novel sorting mechanism.

Preregistered primitive test: [OP-002](../runs/2026-11-14-page-remap/README.md). Closed on this Windows path. Reading each page once erased the apparent mapping gain even with 2 MiB extents.

### 1b. Select the output offset from the merge plan

_Author: agent:gpt-6._

For a returned read-only view that guarantees record alignment, use the sorted merge plan to choose the base pointer's offset within a page. Each sufficiently long single-source slice nominates one of 32 output offsets for 128-byte rows on 4 KiB pages. Summing the eligible bytes per offset identifies the one layout that avoids the most copying. A displaced starting pointer changes the boundary layout and would need an explicit allocation and output contract.

Closest work: the [existing SuperSort page-remapped merge](../runs/2026-11-12-page-remapped-merge-candidate/README.md) and [RUMA radix-partition assembly](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) reuse whole pages and copy partial page boundaries. This diagnostic asks what is gained in overlapping runs by moving the entire output's alignment once, without adding padding between rows. A gain in eligible bytes is insufficient to establish novelty or speed.

[Trip-time coverage test](../runs/2026-11-14-taxi-page-coverage/README.md). One of twelve weekly pairs overlapped. Four rows were in the overlap and selecting an offset gave the same coverage as the aligned output. Keep the offset idea unconfirmed until a substantially overlapping workload is screened.

### 1c. Choose the alignment of each input run before writing it

_Author: agent:gpt-6._

With a page-aligned result, a long slice can be reused only if the starting ranks of that slice in its input and in the merged order agree modulo the number of rows per page. If a producer knows the order of both runs before writing their payloads to mapped storage, it could choose a different starting offset for each input. This might preserve two long slices that require different relative alignments. The best fixed offset for each input can be computed independently by accumulating eligible whole-page bytes for each of the 32 possible offsets. This does not guarantee that a producer can choose the offsets cheaply. The first test is an optimistic coverage calculation under free advance knowledge, with no prototype timing.

Closest work: [RUMA](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) rewires already partitioned pages and handles page boundaries, and [Merge Path](https://arxiv.org/abs/1406.2628) identifies portions of the two input runs at chosen output ranks. Our [prior taxi probe](../runs/2026-11-14-taxi-page-coverage/README.md) can move the output pointer by one fixed offset. The narrower question is what would be gained by instead choosing a distinct, fixed placement for each input before it is materialized. The diagnostic measures eligibility and leaves mechanism novelty open.

[Flight coverage diagnostic](../runs/2026-11-16-flight-overlap/README.md). Fixed per-input offsets raised median coverage from 48.19% to 95.83% for the 20 weekly pairs with any overlap, all of which had at most 3.11% of rows in the shared interval. In the 36 heavily interleaved airport pairs, the longest single-source slice had 17 rows and no page could be reused. Further timing of this layout needs a separate near-disjoint workload and has to include the planning and input construction costs.

### 1d. Place the outer stretches when the producer writes both batches

_Author: agent:gpt-6._

On a chronological pair whose first batch begins and ends first, both long outer stretches can align if the second batch begins at the first batch's row count modulo the rows per page. A binary search in each input finds the stretch that can qualify for mapping. Unaligned boundary rows and the overlap still use a stable merge. For arbitrary ranges, the same rule follows from the source and destination rank of each outer stretch. Two stretches from one input may request incompatible offsets, so keep the longer qualifying stretch in that case.

[RUMA](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) assembles partitioned pages, and the [prior Linux prototype](../runs/2026-11-12-page-remapped-merge-candidate/README.md) maps slices of already laid out runs. Independent placement chooses the source offset before its first mandatory write, with just endpoint searches for the outer stretches. A producer that needs to retain both contiguous batches and the contiguous merged view could avoid a second write of most of the wide records. A fused direct writer can already load each record once and produce both kinds of output, so it must be a reference. The origin platform's mapping and first-read costs must also fit in the savings budget.

[End-to-end timings](../runs/2026-11-16-producer-page-placement/README.md). At 2% overlap the shifted layout raised coverage from 49% to about 98%. It achieved 0.412–0.543× against the fastest direct reference on Windows across the four primary cases. The costs of materializing both batches and first access through the new mapping close this implementation on Windows.

### 1e. Measure the producer contract with native Linux mappings

_Author: agent:gpt-6._

Use the same outer-slice placement from 1d with a Linux memory-backed file and address aliases. In an earlier Linux merge experiment, the caller already had prepared inputs. This experiment includes producing both batches and the final view, and races against a direct writer that fills the outputs in one traversal. Also try populating the page tables while installing the read-only aliases, with that time inside the same end-to-end interval. The two variants isolate whether delaying alias setup into the first scan helps on this host.

[RUMA](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) is the closest prior work on mapping-based assembly. Linux [`mmap`](https://man7.org/linux/man-pages/man2/mmap.2.html) already exposes eager population. This run tests a specific platform and output contract for the existing producer placement mechanism. Its preregistered comparisons and stopping rule are in the [Linux protocol](../runs/2026-11-16-linux-producer-placement/protocol.md).

**Result.** The adjusted Linux variants gave 1.231–1.280× on the eight fresh holdout cases and cleared the 77% threshold in zero. Constructing the shareable batches took 80–84% of the measured time. This closes the tested producer path that creates both batches by copying from the original buffers. [Measured result](../runs/2026-11-16-linux-producer-placement/README.md)

## 2. Compressed keys in flight for bandwidth-bound regimes

**Idea.** After a most-significant-digit pass, the bucket already encodes the high bits. Write the remaining keys in a narrower packed format (for example 3 bytes instead of 4, or deltas) so later passes move fewer bytes, and rebuild full keys only at the end.
**Why it could matter.** In multithreaded runs on large arrays, cores wait for memory. Trading cheap arithmetic for bandwidth may pay off there, even though it did not inside cache (prior E052 packed only in-cache leaves).
**Known nearby.** Key compression in database sorting, prefix truncation, radix sort with key reduction.
**Kill test.** Measure multithreaded streaming bandwidth (STREAM-like) against the packing and unpacking throughput per core. Proceed only if packing is clearly faster than the memory traffic it saves.

**2026-11-15 bandwidth screen (author: agent:codex).** Wassenberg and Sanders already approach peak per-pass memory bandwidth with software write combining. Lemire and Boytsov already show SIMD packing of integers into fixed-width blocks. FractalSort uses compressed radix histograms for wide keys in hardware. The limited question here is whether folding the known prefix into bucket metadata and moving 24 bits per key can pay for CPU conversion across multiple DRAM transfers. Prefix truncation and SIMD packing are established techniques. A measured margin would justify testing a distinct pass-elimination or cache-residency mechanism. [Wassenberg and Sanders](https://arxiv.org/abs/1008.2849) · [Lemire and Boytsov](https://arxiv.org/abs/1209.2137) · [FractalSort](https://doi.org/10.1109/TC.2026.3653702) · [Preregistered screen](../runs/2026-11-15-compressed-key-bandwidth/protocol.md)

**Result.** With eight workers, three-byte transfers plus conversion estimated 1.086–1.178× with two intervening transfers. Zero of four primary cases reached 1.30×. Equivalent passes with equal effective bandwidth give only 1.231× in the logical traffic model. Close width reduction alone for this pipeline. [Results](../runs/2026-11-15-compressed-key-bandwidth/README.md)

## 3. Payload permutation for records

**Idea.** Sorting records (rows of 16–128 bytes) by key is common and the references move whole records repeatedly. Sorting packed key-plus-index words is known. The open part is the final permutation of the payloads: find a new cache-, TLB- and bandwidth-aware way to apply it (for example in blocks guided by the sort's own bucket structure, or combined with idea 1).
**Why it could matter.** For large records the permutation dominates the run time and is usually done as a naive gather.
**Known nearby.** Argsort plus gather, normalized keys in DuckDB, IPS4o on records, vqsort key-value pairs.
**Kill test.** Measure the obvious baseline (vqsort argsort plus gather) against an ideal sequential copy of the same bytes. If the gap is small, the permutation has no room for a large gain.

**2026-11-12 investigation (author: agent:gpt-6).** Inoue and Taura already identify random payload reads as the bottleneck and avoid them with cache-sized sorts followed by a SIMD multiway merge. DuckDB already separates normalized keys from payloads and reorders payloads after key sorting. IPS⁴o already moves data in cache-friendly blocks. These cover the bottleneck and the main building blocks. The narrower hypothesis is that the final ranks of large records can be grouped into cache-resident destination ranges, with source-ordered reads inside each range and no intermediate copy of the payload. The added work on indices must cost less than the reduction in cache and TLB misses. Novelty relative to existing blocked permutation methods remains unverified. [Inoue and Taura](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf) · [Kuiper and Mühleisen](https://duckdb.org/pdf/ICDE2023-kuiper-muehleisen-sorting.pdf) · [Axtmann et al.](https://arxiv.org/abs/2009.13569)

The [preregistered pilot](../runs/2026-11-12-record-permutation/README.md) cleared the headroom threshold on five of eight workloads. The best case estimated 1.367–1.399× across two seeds when substituting sequential-copy cost for the gather phase. [Pilot results](../runs/2026-11-12-record-permutation/summary.md)

The [blocked permutation probe](../runs/2026-11-12-blocked-permutation/README.md) tests one specific mechanism. It uses each destination range as a cache-resident window and sorts its descriptors by original position in the existing index buffer. The payload moves only once. This differs from the cache-sized local record sorts followed by payload merging in Inoue and Taura. Multi-pass locality-aware gather and scatter are also prior art on GPUs. The probe asks whether this particular mapping of final ranks to CPU cache windows pays for its index sort, even against an ordinary gather with software prefetch. [Inoue and Taura](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf) · [He et al.](https://www.microsoft.com/en-us/research/publication/efficient-gather-and-scatter-operations-on-graphics-processors/)

**Result.** Closed the tile-and-sort design after it missed the threshold in all eight cases. Its end-to-end speedup was 0.542–0.648× against the fastest measured reference. Gather with software prefetch won every paired repetition, making it a useful control for any future permutation experiments under this contract. [Probe results](../runs/2026-11-12-blocked-permutation/summary.md)

### 3a. Group permutation requests by source within a destination window

_Author: agent:gpt-6._

Keep a window of final output positions resident in cache. Count its requests by source band and group them using one 32-bit word per request: an offset in the source band and a slot in the current destination window. Walk the source bands one at a time and write each row directly to its final slot. This preserves one payload movement per row. Grouping narrows the address range of concurrent source reads and could reduce repeated page translations enough to pay for two passes over the indices and nonsequential stores within the window.

Closest work: [Inoue and Taura (2015)](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf) bound random access in row sorting via per-merge run IDs and sequential cursors, moving rows at merge stages. This candidate keeps one final materialization and groups requests within a finished permutation. The underlying two-sided locality strategy also appears in [cache and TLB blocking for sparse matrix-vector multiplication](https://jeewhanchoi.github.io/publication/pdf/spmv_book.pdf), so cache blocking by itself is established prior art. The question here is whether the packed, per-window schedule pays for itself on a one-use sort permutation. No novelty claim has been established.

Preregistered budget and end-to-end kill test: [OP-001](../runs/2026-11-14-record-permutation/README.md). Closed after the test. The grouped version took 22.8–22.9% longer than the fastest measured reference on the primary workload.

## 4. Batches of small sorts across SIMD lanes

**Idea.** Many workloads sort many independent small arrays (groups, windows, per-key lists). Sort them together, with each SIMD lane or vector handling a different array, instead of calling a sorter once per array.
**Why it could matter.** For about 1,000 elements, call overhead, branch mispredictions and partially used vectors dominate.
**Known nearby.** Batched sorting networks on GPUs, segmented sort.
**Kill test.** Compare a per-array call of the best small-array sorter with a transposed network over 8 arrays of the same size, including the transpose cost.

## 5. Exact rank computation without data movement

**Idea.** Compute each key's final position (its rank) with branch-free SIMD comparisons or counting inside cache-sized blocks, then write every key exactly once to its destination.
**Why it could matter.** Each key is written once; there is no recursive partitioning and no mispredicted branch.
**Known nearby.** Rank and counting sorts, merge-path ranking, LearnedSort (Kristo et al., 2020), which predicts positions approximately.
**Kill test.** Rank sort of a block that fits in L1 or L2 against the best in-cache network sort at the same size.

### 5a. Invert four stable ranks with AVX2 shifts and ORs

_Author: agent:gpt-6._

Consider independent groups of four packed 32-bit records with 16-bit sort keys and 16-bit payloads. Compare each key tagged with its original slot against its three partners. The count of wins is its stable rank. Within each 128-bit half, shift each source lane number into the byte specified by its rank, OR the four results together, and unpack those four bytes as the AVX2 permutation control. One final permute moves the original records. This keeps ranks, inverse indices and records in registers, with no dependent loads for permutation control. The cost of variable shifts and horizontal ORs may outweigh fewer payload shuffles or lookup loads.

Closest work: [Chhugani et al. (2008)](https://www.vldb.org/pvldb/vol1/1454171.pdf) and [djbsort](https://sorting.cr.yp.to/internals.html) use SIMD-lane sorting networks. [Mimicry Sort4 (2023)](https://www.mimicry.ai/blog/faster-sorting-beyond-deepminds-alphadev/) maps the six comparison bits to an in-register shuffle through a memory table. [Texas Instruments, US20230037321A1](https://patents.google.com/patent/US20230037321A1/en) describes rank-based hardware vector permutation with stable ranks and inversion of the input-to-output map. The unverified difference is packing and inverting two four-way permutations entirely in AVX2 registers using ranks as byte offsets. The test measures that implementation choice against a known SIMD lookup and a direct SIMD network.

Preregistered batch test: [OP-003](../runs/2026-11-14-four-row-ranks/README.md). Closed after the test. In-register rank inversion was slower than the fastest direct SIMD reference on both primary seeds and on the controls.

## 6. Helper threads for memory-level parallelism

**Idea.** In a multithreaded run, dedicate some hardware threads (SMT siblings) to prefetching or to producing histograms ahead of the threads that move data.
**Why it could matter.** It could hide memory latency that out-of-order execution cannot hide on irregular scatters.
**Known nearby.** Helper-thread prefetching in the architecture literature.
**Kill test.** Measure a scatter-bound pass with and without a helper on the SMT sibling, using the same total thread count as the reference.

**2026-11-15 gather screen (author: agent:codex).** Collins et al. already use SMT threads to execute future loads, and Ainsworth and Jones establish in-thread software prefetch for indirect memory references. A finished record permutation exposes every future source address through a sequential index stream. Instead of generating a separate address trace, a helper can read that stream directly with a bounded lead while the worker writes the destination sequentially. The open practical question is whether that helps enough to give up a second writer or the worker's own prefetches. This tests helper prefetch as an established mechanism and would need a separate algorithmic contribution to qualify as a finding. [Collins et al.](https://cseweb.ucsd.edu/~tullsen/isca2001.pdf) · [Ainsworth and Jones](https://doi.org/10.17863/CAM.38025) · [Preregistered screen](../runs/2026-11-15-smt-gather-helper/protocol.md)

**Result.** On 256 MiB of uniformly permuted 128-byte rows, the fastest cached helper achieved 0.564× and 0.629× of the best equal-affinity split gather. The helper beat one writer by 1.16–1.46× on the same runs. Two dedicated writers retained the lead with cached stores and on two physical cores. This closes bounded helper lookahead for this materialization workload. [Results](../runs/2026-11-15-smt-gather-helper/README.md)

## 7. Bitplane membership sorting for short stable batches

_Author: agent:gpt-6 (Codex), 2026-11-22._

Transpose 32 ordinary uint8 keys into eight 32-bit membership planes with AVX2
movemask. Traverse prefixes by intersecting scalar masks, emitting equal-key
source slots in increasing position. Only the final output moves payloads.
This could remove intermediate shuffle/compare-exchange work for short stable
record sorts. Scalar traversal and branch entropy may erase that benefit.

Closest known work: [bit-sliced index arithmetic and top-k selection (2001)](https://www.cs.umb.edu/~poneil/SIGBSTMH.pdf),
[SIMD bitwise MSB radix sorting (2021)](https://www.ti.uni-bielefeld.de/downloads/publications/simdRadixSort.pdf),
and [AVX2 networks (2021)](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SEA.2021.3).
The unconfirmed implementation-level difference is keeping the entire local
permutation in original-position masks after one vector bit transpose instead
of partitioning keys or payloads at each radix level. Bitmap refinement itself
is established prior art; no algorithmic novelty is claimed by this screen.
This changes the mechanism from the failed numeric-rank inversion experiment.

Cheap kill test: stable batches of 32 byte keys with uint32 payloads, ordinary
input and output, all conversions included. Beat a direct batched AVX2 tag
network, pinned SIMD libraries and stable counting sort at 77% of best time on
both registered uniform-key seeds before trying held-out inputs.
[Protocol](../runs/2026-11-22-bitplane-sort/protocol.md).

**Result (2026-11-22, author: agent:gpt-6).** Closed the scalar prefix traversal
after the first registered screen. Uniform byte-key batches took about 225
ns/group versus 36.6-39.4 for the direct AVX2 16-bit tag network: 0.163-0.175x.
The eight-key controls reached only 0.462-0.464x. All 240 timed calls verified.
The strongest reference also moves payloads only at the end, so avoiding
intermediate payload movement alone does not create an advantage here.
No novelty or held-out performance claim is established.
[Measured result and raw samples](../runs/2026-11-22-bitplane-sort/README.md).

## 8. Sparse saved-row cuts for interleaved in-place permutation

_Author: agent:gpt-6 (Codex), 2026-11-22._

After sorting `(key, source_index)` tags, apply the resulting gather permutation
inside the original record array. Save the original records at up to 64
regularly spaced positions. Each saved position starts a walker; a walker stops
when its next source is any saved position, using the saved original row to
close that segment. Interleave the independent segments on one hardware thread,
issuing their record prefetches before their copies. Mark processed destinations
in the private index tags. Finish cycles containing no saved position with the
ordinary cycle leader. No preliminary traversal is needed to discover segments.

The proposed gain has two parts: expose independent memory requests even within
one long permutation cycle, and avoid the full-size gather destination plus
copy-back pass. Fixed row checkpoints cost at most 64 record copies and a cheap
index-mask test. The risks are serial uncovered cycles, a long last segment,
random tag traffic, writeback traffic and scheduling overhead.

Closest work: [Fich, Munro and Poblete, Permuting in Place (1995)](https://doi.org/10.1137/S0097539792238649)
establish cycle-leader permutation; [Gustavson, Karlsson and Kagstrom (2010)](https://webapps.cs.umu.se/uminf/reports/2010/005/part1.pdf)
identify poor locality in cycle walks and schedule known matrix-transposition
cycles; [IPS4o](https://arxiv.org/abs/2009.13569) moves blocks in place; and
[Boost block_indirect_sort](https://www.boost.org/doc/libs/latest/libs/sort/doc/html/sort/parallel.html)
uses indirect blocks. Cycle walking, prefetching and multiple independent loads
are established techniques. The hypothesis to audit is the use of sparse saved
rows to split an arbitrary record permutation into safe independent streams
without a cycle-discovery or inverse-permutation pass. Novelty is unconfirmed.

This is different from the closed source-regrouping experiments: it preserves
the caller's output address, never regroups descriptors into destination tiles,
and never allocates a full second payload array inside the candidate.
[Preregistered kill test](../runs/2026-11-22-checkpoint-cycles/protocol.md).

**Result (2026-11-22, author: agent:gpt-6).** Closed the fixed 64-checkpoint
version under the registered reusable-workspace contract. The full sort took
52.286-53.004 ms versus 48.150-48.696 for the strongest measured reference,
vqsort plus prefetched streaming gather and streaming copy-back: 0.908-0.931x.
It beat ordinary cycle rotation by 2.38-2.47x but not the project's gate. All
216 calls passed exact row verification; 46,410 supplied permutations and
66 additional full-sort checks also passed. The candidate only requires tags
and small saved-row state; the harness nevertheless supplied full payload
scratch to every method, so no peak-memory improvement was measured. Do not
relabel the current data with a memory cap or call the slower baseline a win
against the fastest reference. [Results](../runs/2026-11-22-checkpoint-cycles/README.md).

## 9. Move unchanged spans directly after a batch of key corrections

_Author: agent:gpt-6.2-sol (Codex), 2026-11-23._

Consider a sorted, contiguous array of wide records and a batch of replacements
for their sort keys, with each original position supplied by the caller. Keep
the old keys intact while finding the insertion gaps for the new keys. Combine
those gaps with the deleted positions. The number of inserts minus deletions
before a span gives the displacement shared by every row in that span.

Move left-shifting spans in ascending source order and right-shifting spans
in descending source order. The mapping from unchanged sources to final
destinations is increasing, so these orders preserve sources that still need
to be read. Fill the remaining destinations with the updated rows. A span at
zero displacement stays in place. Each other unchanged row moves once in an
overlap-safe bulk copy. The plan and saved rows use space proportional to the
number of corrections. The full-array scan and second write of global
compaction followed by merge are avoidable on this input contract.

[DeltaSort (Dwivedi, SEA 2026)](https://doi.org/10.4230/LIPIcs.SEA.2026.18)
already uses a list of dirty indices, then places updated values through
bounded binary insertions. Its extract-sort-merge (ESM) control first compacts
unchanged rows, then merges the sorted updates back. A [Go slices proposal
for Move](https://github.com/golang/go/issues/79768) discusses doing a single
row move with one overlap-safe copy. The proposed difference here is computing
an event plan before applying a **batch** of corrections and scheduling both
displacement directions so an unchanged row never moves twice. The intact old
order is part of this interface. Prior work establishes these building blocks,
and the novelty of their batch scheduling still needs independent review.

The cheap test races upstream DeltaSort and two bulk ESM directions under the
same correction interface, with allocations included. The payoff depends on
the number and spacing of moves and the cost of searching the old key order.
[Preregistered test](../runs/2026-11-23-key-correction-spans/protocol.md)

**Result (2026-11-23, author: agent:gpt-6.2-sol).** On four fresh uniform
replacement cases the prototype achieved 1.810–2.102× over the fastest bulk
ESM direction at 128 and 256 MiB. It wrote about half as many unchanged rows.
Adding DriftSort on four other fresh inputs preserved 1.944–2.029×. Upstream
DeltaSort won the local-change controls. The owner received the result after
the development test passed the 1.5× threshold. Independent novelty review
and application traces remain open. [Reported measurements](../runs/2026-11-23-key-correction-spans/README.md)

**Flight replay (author: agent:gpt-6.2-sol, 2026-11-23).** Test the frozen
implementation against DeltaSort and bulk compaction and merge when the key
corrections come from reported departures. Bound the merge to the affected
interval in two controls. The comparison isolates the cost to maintain the
ordered array when positions are already provided. [Registered replay](../runs/2026-11-23-flight-key-corrections/protocol.md)

**Replay result (author: agent:gpt-6.2-sol, 2026-11-23).** The median
relative speed was 0.775× after flushing and 0.761× after a copy reset.
No day met the registered time limit. DeltaSort was the fastest reference in
50 of 56 day and cache combinations. The median day required four writes of
unchanged rows and the candidate made exactly that many. This closes the
tested flight replay. Preserve interval-limited ESM as a control when
replacement keys are clustered. [Measured replay](../runs/2026-11-23-flight-key-corrections/README.md)

## Rejected or out of scope

- Dispatching between known sorters by detected distribution (the prior E054 approach). This is a combination of known techniques, not a finding under the current goal, though it may still be useful inside a library.
