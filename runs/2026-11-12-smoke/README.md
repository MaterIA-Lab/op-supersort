# Continuity smoke test — 2026-11-12

Checked that the prior local runner compiles and executes in the new preparation workspace on Windows with GCC 16.1. The run used 1,000 `uint32` elements, `uniform` and `few`, seeds 271 and 811, five algorithms and three measured repetitions. All outputs were checked by the runner against `std::sort`; 60 timed samples were recorded.

This is a technical smoke test, not a preregistered evaluation of the new goal and not evidence that the goal was met. It uses a small, incomplete matrix and only one thread. The full local snapshot includes third-party vendor sources not redistributed here. The published metadata replaces the local user path with `<local-user>`; raw timing values and source snapshots are preserved. Model identifier, token count and cost for this setup session were not captured; do not infer them.
