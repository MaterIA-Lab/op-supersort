# Compressed-key bandwidth probe

Windows x64, AVX2 and GCC with C++20 threading support are required. The timed matrix requires eight physical cores and approximately 1 GiB of available RAM. The program prints a CSV to standard output. The smoke mode checks the conversions and runs a small one-worker case.

```powershell
New-Item -ItemType Directory -Force lab/compressed-key-bandwidth
g++ -std=c++20 -O3 -mavx2 -DNDEBUG -Wall -Wextra -Werror prototypes/agents/compressed-key-bandwidth/bench.cpp -o lab/compressed-key-bandwidth/bench.exe
.\lab\compressed-key-bandwidth\bench.exe --smoke
python -c "from pathlib import Path; import subprocess; out = Path('lab/compressed-key-bandwidth/reproduction.csv'); subprocess.run(['lab/compressed-key-bandwidth/bench.exe'], stdout=out.open('xb'), check=True)"
python -X utf8 runs/2026-11-15-compressed-key-bandwidth/analyze.py lab/compressed-key-bandwidth/reproduction.csv
```

Each AVX2 pack operation shuffles out the common prefix and stores exactly 48 bytes for 16 keys. Unpacking reconstructs the prefix for each key. A scalar generator constructs both representations for verification. The probe tests buffer traffic without sorting. [Results and protocol](../../../runs/2026-11-15-compressed-key-bandwidth/README.md)
