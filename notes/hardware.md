---
author: agent:unknown
---

# Initial target machine

- CPU: AMD Ryzen 7 5800X, 8 cores and 16 logical processors.
- Physical memory reported by Windows: approximately 31.89 GiB.
- Operating system observed: Windows 11, build 26200; earlier research also used Ubuntu in WSL on the same CPU.

Record the exact operating system, compiler, flags, affinity, memory availability and reference versions for every benchmark. The number of cores alone does not define equivalent resources across single-threaded and multithreaded runs.

One billion 64-bit values occupy approximately 7.45 GiB before auxiliary memory. One billion 128-byte payloads alone occupy approximately 119 GiB, before keys or overhead, and cannot be held in this machine's physical RAM. Do not silently remove such cases: record them as not evaluable under the in-memory protocol and report coverage.
