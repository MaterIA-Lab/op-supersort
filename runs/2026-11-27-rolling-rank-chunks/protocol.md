# Registered screen for packed rank groups

## Workload

One immutable series of `uint32_t` keys in RAM. For every stride-one
window, emit all absolute `uint32_t` input indices into a dense
window-major array. Sort by key and break ties by increasing source
index. The caller supplies an already allocated and touched output.
All methods use one pinned CPU thread. This covers offline rolling
argsort, where a consumer needs every rank of each short window.

| Stage | Windows | Width | Key distribution | Seeds |
|---|---:|---:|---|---|
| Development, primary | 131,072 | 32 and 64 | Uniform uint32 | 83179 and 152083 |
| Development, control | 131,072 | 32 and 64 | Uniform over 16 distinct keys | 83179 and 152083 |
| Holdout, conditional | 131,072 | Passing widths | Uniform uint32 | 273289 and 417841 |

Use the low 32 bits of successive SplitMix64 outputs. For the control,
keep the low four bits. The input length is `windows + width - 1`.
Output sizes are 16 and 32 MiB. The group width is eight and the tile
contains up to 32 windows. Both sizes retain these settings for the
entire screen. The development seeds, widths and distribution are
fixed before implementation and timing.

## Methods

- `window_vq`: pack `(key, index)` into uint64, sort each window with
  Highway VQSort and extract the indices.
- `rolling_binary`: maintain sorted keys and indices in small arrays.
  Find the expiring and arriving positions by binary search, then
  move the affected interval and copy the index array to output.
- `rolling_simd` and `rolling_stream`: use two AVX2 rank comparisons
  per eight keys for the same update. Emit the indices with cached or
  non-temporal stores, respectively.
- `rolling_direct`: use the SIMD rank search and maintain the sorted
  key array. Build each output row directly from unchanged spans of
  the previous output row and the incoming index.
- `union_walk`: one VQSort over the tile's union, a membership mask
  over union ranks and scalar enumeration using trailing-zero count.
- `union_pack`: the same sorted union with AVX2 lane packing for all
  rank groups in every window.
- `union_cache` and `union_cache_stream`: retain packed vectors and
  update only the one or two groups that changed. Write cached output
  directly, or assemble a row in L1 and stream it to output.

The first seven methods are references. The two cached-group
implementations are the candidate variants. Each timed call includes
preprocessing, every sort, group setup, output writes, and any store
fence. The output and input are flushed before each call. Generation,
common buffer allocation, and verification are outside the timer.
Use two warm-ups and seven measured calls per method and input, in a
deterministically shuffled order per round. Check every output against
per-window `std::stable_sort` of input indices. Verify edge fixtures
for ties, unsigned boundaries, partial tiles and tail writes before
timing.

## Decision rule

For a given width, continue only if a single candidate variant takes
at most 77% of the fastest reference median on both primary seeds.
If that screen passes, rerun with the same binary on the holdout seeds
for the passing width. Compare all methods again. The duplicate-key
controls report sensitivity to ties and provide correctness coverage.
The registered inputs are synthetic. A timing win needs a separate
test on a real series before establishing practical relevance.
