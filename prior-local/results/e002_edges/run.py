"""Reproducible CPU-only sorting experiments, standard-library Python orchestration."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import statistics
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SOURCES = {
    'pdqsort.h': 'https://raw.githubusercontent.com/orlp/pdqsort/master/pdqsort.h',
    'ska_sort.hpp': 'https://raw.githubusercontent.com/skarupke/ska_sort/master/ska_sort.hpp',
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sizes', nargs='+', type=int, default=[100000, 1000000, 10000000])
    p.add_argument('--distributions', nargs='+', default=['uniform'])
    p.add_argument('--seeds', nargs='+', type=int, default=[42])
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--tag', default='pilot')
    args = p.parse_args()
    if min(args.sizes) < 0 or args.repeats < 1:
        p.error('sizes must be nonnegative; repeats must be positive')
    vendor = ROOT / 'vendor'
    vendor.mkdir(exist_ok=True)
    hashes = {}
    for name, url in SOURCES.items():
        target = vendor / name
        if not target.exists():
            target.write_bytes(urllib.request.urlopen(url).read())
        hashes[name] = {'url': url, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    exe = build / 'bench.exe'
    flags = ['g++', '-O3', '-march=native', '-DNDEBUG', '-std=c++17', str(ROOT / 'bench.cpp'), '-o', str(exe)]
    subprocess.run(flags, check=True)
    out = ROOT / 'results' / args.tag
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(ROOT / 'bench.cpp', out / 'bench.cpp')
    shutil.copy2(Path(__file__), out / 'run.py')
    meta = {'utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
            'compiler': subprocess.check_output(['g++', '--version'], text=True),
            'flags': flags, 'arguments': vars(args), 'vendor': hashes,
            'source_sha256': hashlib.sha256((ROOT / 'bench.cpp').read_bytes()).hexdigest(),
            'timing': 'single-thread; allocation included; input copy and correctness excluded; one warmup per case; shuffled algorithm order'}
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    rows = []
    with (out / 'raw.csv').open('w', newline='') as f:
        writer = None
        for n in args.sizes:
            for dist in args.distributions:
                for seed in args.seeds:
                    print(f'Running n={n} distribution={dist} seed={seed}', flush=True)
                    result = subprocess.run([str(exe), str(n), str(args.repeats), dist, str(seed)], text=True, capture_output=True, check=True)
                    batch = list(csv.DictReader(io.StringIO(result.stdout)))
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=batch[0].keys())
                        writer.writeheader()
                    writer.writerows(batch)
                    f.flush()
                    rows.extend(batch)
    groups = {}
    for r in rows:
        groups.setdefault((int(r['n']), r['distribution'], r['algorithm']), []).append(float(r['ms']))
    lines = ['# Resultados', '', 'Medianas en ms. Véase metadata.json para condiciones y raw.csv para muestras.', '', '| n | distribución | algoritmo | mediana ms |', '|---:|---|---|---:|']
    for (n, dist, algo), values in sorted(groups.items()):
        lines.append(f'| {n} | {dist} | {algo} | {statistics.median(values):.4f} |')
    (out / 'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
