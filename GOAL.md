# SuperSort: research goal

Can a genuinely new idea that exploits how a computer works (SIMD units, caches, TLB and virtual memory, memory bandwidth, multiple cores, or any other component of the machine) make sorting **substantially faster** than the best existing implementation for a practically relevant task?

The project searches for such an idea, iteration after iteration, until a relevant finding appears. Sorting numeric keys, records and objects, at any size and in single- or multithreaded mode, are all in scope. The prior local SuperSort research is background, not a constraint: see [notes/prior-research.md](notes/prior-research.md).

## What counts

**Innovation is required.** Each idea must state what is new relative to the closest known work and why its mechanism could yield a large gain (for example less memory traffic, fewer passes, fewer instructions or mispredictions per key). The following do not count as findings: tuning parameters of existing libraries, patching phases of an existing sorter, or dispatching between known algorithms. Known techniques are welcome as references and as building blocks when the new mechanism is what produces the gain.

**Relevant finding:** on a declared workload class of practical relevance (data layout, key type, distribution, size range, thread mode), SuperSort takes **at most 77% of the time (≥1.3×)** of the fastest competitive reference, on fresh inputs not used during development, with every output verified correct.

**Very relevant finding:** at least **1.5×** on an important class, such as random keys, records sorted by key, or large arrays, or a new mechanism that clearly opens a line of work. When this happens, notify the owner (a GitHub issue labelled `major-finding` or a direct report) and pause broad exploration until the owner decides whether to dedicate the research to it.

If neither happens, keep exploring new ideas. Publish every negative result with its cause, as far as it is known.

## Fair comparison

- References are the strongest available implementations for the same task and contract, including the obvious strong solution for that class, not only `std::sort`. Record versions and build flags.
- Use the same thread count and machine. Time allocation, copies and conversions that the user would pay. Data starts and ends in main memory.
- Declare the workload class and inputs before measuring the candidate on them. Do not choose inputs, seeds or classes after seeing results.
- Verify the output of every run. A faster but incorrect result does not count.
- Record hardware, software, raw samples and limitations. Report the scope honestly: a win on one class is not a win on all.

The intended deliverable of a finding is a reusable library with a simple interface and examples, in `prototypes/humans/`.
