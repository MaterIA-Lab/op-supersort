---
author: agent:codex
---

# Preregistered bandwidth screen for 24-bit keys

The backlog proposes dropping the high byte once a radix bucket already encodes it. This screen asks whether the smaller intermediate pays for encoding and restoring ordinary `uint32_t` keys when several transfers go through main memory. It measures movement and conversion with sequential access. A pass could justify a scatter prototype, while any end-to-end sorter would still have to pay for classification, allocation, scatter and exact ordering.

## Declared matrix

- Primary: `2^24` and `2^26` keys, eight workers on distinct physical cores, SplitMix64 seeds 104729 and 130363. Four workers at both sizes and one worker at `2^24` are controls. The upper byte is constant per run and reconstructed from the supplied prefix. The 24 suffix bits are random. Inputs are constructed independently in both representations.
- Reusable 64-byte-aligned buffers, disjoint input and output, pre-touched before each timing. Poison the destination and sweep a shared 128 MiB eviction buffer before release of the workers. Measure a full operation through the completion barrier, including the store fence for streaming kernels. Allocation, initial generation, poisoning, cache sweep and exact byte verification are outside timing for every method. There is one warm-up and seven measured rounds per case. Rotate the six method positions and reverse the rotation on odd rounds.
- Full- and narrow-width transfers each have two controls: multithreaded `memcpy` and AVX2 non-temporal copy, using the same number of workers and CPU placement as AVX2 pack/unpack. Check every output against its independent full-width or packed reference. Test both conversions on boundary values before timing.

## Decision rule

In each case `C32` and `C24` are the fastest median full- and narrow-width transfers, `P` is pack and `U` is unpack. Report `C32/C24` as the isolated transfer ratio and report the estimates `3*C32/(P+C24+U)` and `4*C32/(P+2*C24+U)` for one and two equivalent interior transfers respectively. These are sums of independently measured phase medians, without any credited saving in sorting or changes in cache residency.

Advance this width-only design only if the two-interior-transfer estimate reaches 1.30 on both sizes and both primary seeds. Two separate main-memory transfers after the prefix is known already give the proposal a generous budget for a 32-bit radix pipeline. Record controls and each seed even if the decision is already clear. A sequential result cannot establish a sorting speedup. A narrower format that changes the number of passes or moves a working set across a cache boundary needs its own hypothesis and control.

The logical traffic calculation with `k` interior transfers is `8(k+2)` bytes per key at full width and `14+6k` with a 24-bit intermediate. This is a constant-bandwidth model for equivalent passes, with streaming stores and no representation-induced change in residency. It is independent of the measured test.
