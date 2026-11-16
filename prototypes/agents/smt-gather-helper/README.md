# Helper-thread gather probe

This Windows AVX2 microbenchmark applies a supplied permutation of 128-byte records. It queries processor topology to compare two hardware threads of one core with two separate cores. The timed matrix uses about 656 MiB of memory at its largest point. GCC with C++20 threading support is required.

```powershell
New-Item -ItemType Directory -Force lab/smt-gather-helper
g++ -std=c++20 -O3 -mavx2 -DNDEBUG -Wall -Wextra -Werror prototypes/agents/smt-gather-helper/bench.cpp -o lab/smt-gather-helper/bench.exe
.\lab\smt-gather-helper\bench.exe --smoke
python -c "from pathlib import Path; import subprocess; out = Path('lab/smt-gather-helper/reproduction.csv'); subprocess.run(['lab/smt-gather-helper/bench.exe'], stdout=out.open('xb'), check=True)"
python -X utf8 runs/2026-11-15-smt-gather-helper/analyze.py lab/smt-gather-helper/reproduction.csv
```

The `requested` column counts records for which the helper issued two memory requests. The foreground worker publishes a boundary every 128 rows. The helper skips past that boundary and advances to the fixed lookahead limit. The direct split variants produce disjoint halves of the output. [Protocol and measurements](../../../runs/2026-11-15-smt-gather-helper/README.md)
