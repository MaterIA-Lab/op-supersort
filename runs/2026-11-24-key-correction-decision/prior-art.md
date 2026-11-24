# Prior art for the direct-span schedule

Author: agent:gpt-6.2-sol (Codex), 2026-11-24.

## Closest operations

- [Burns and Long, In-Place Reconstruction of Delta Compressed Files, 1998](https://research.ibm.com/publications/in-place-reconstruction-of-delta-compressed-files)
  schedules copy ranges so a write preserves any unread input. Its full
  algorithm builds a dependency graph, schedules copies in topological order,
  saves data for cycles, and performs adds last. It also describes choosing
  a safe direction within an overlapping copy. These operations predate
  the SuperSort prototype.
  [Full paper, sections 4.1 and 4.2](https://www.crss.us/media/pubs/1e38dfef5b6289881f47ad0cd35bb4c509f6af3e.pdf)
- [Dwivedi, DeltaSort, SEA 2026](https://doi.org/10.4230/LIPIcs.SEA.2026.18)
  maintains a contiguous sorted array with known dirty positions. Its
  contract starts after those keys have changed. The paper also describes
  Extract–Sort–Merge, which saves the changed rows, compacts the other rows,
  and merges back into the array. SuperSort's intact old order lets it use
  binary searches for every replacement before it modifies any row.
- [Geffert, Katajainen and Pasanen, Asymptotically Efficient In-Place Merging, 2000](https://doi.org/10.1016/S0304-3975(98)00162-5)
  bounds data movement for merging adjacent sorted runs in place. The
  tracked corrections here can leave holes throughout the original array
  and supply the changed values separately.

## What the specialization guarantees

For an unchanged row at source index `s`, let `D(s)` be the number of
deleted originals before it and let `I(s)` be the number of new rows
ordered before it. Its destination is `s + I(s) - D(s)`. Planning the
insertions against the intact array yields contiguous ranges with one
common displacement. Both source and destination intervals for unchanged
rows are disjoint and in increasing order.

Consider a left move. Any later unchanged source starts beyond its write
range. An earlier source that stays or moves right ends at or before its
own destination end, which is before the current write range. Visiting left
moves in source order therefore preserves all unread data. The symmetric
argument applies to right moves in reverse order after the left moves.
The new rows fill their reserved slots after both passes. Each displaced
unchanged row is written once and each stationary unchanged row stays put.

This monotone mapping avoids a dependency graph in the implementation.
A general interval scheduler could also enumerate overlaps in linear time
for these two disjoint ordered interval families. The specific contribution
to assess is the planning from sparse key updates followed by these two
passes, with linear scratch in the number of edits. The review establishes
precedent for the copy scheduling principle and leaves priority for this
specific specialization unverified.
