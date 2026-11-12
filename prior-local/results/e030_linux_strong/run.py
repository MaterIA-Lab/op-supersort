"""Reproducible CPU-only sorting experiments, standard-library Python orchestration."""
import argparse
import csv
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SIMD_COMMIT = '6e059b14975df2e3c74260ec905167a1be5a34ca'
HIGHWAY_COMMIT = 'a3f6f68fcc368e5e3025ca25805eabda9d8a456f'
IPS_COMMITS = {'ips2ra': '83f6b76ca308b277b2acc3a36426a3baa3c9cb73', 'ips4o': '08a5b926ee65cef19139057c6bde02bb5542c1cb'}
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
    p.add_argument('--algorithms', nargs='+', help='Optional subset of algorithm names')
    p.add_argument('--quiet', action='store_true', help='Save summary without printing its entire table')
    p.add_argument('--cpu', type=int, help='Pin runner and inherited child processes to a logical CPU')
    args = p.parse_args()
    if min(args.sizes) < 0 or args.repeats < 1:
        p.error('sizes must be nonnegative; repeats must be positive')
    if args.cpu is not None:
        if platform.system() == 'Linux':
            os.sched_setaffinity(0, {args.cpu})
        elif platform.system() == 'Windows' and 0 <= args.cpu < 64:
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
            if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 1 << args.cpu):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            p.error('Unsupported CPU affinity request')
    vendor = ROOT / 'vendor'
    vendor.mkdir(exist_ok=True)
    hashes = {}
    for name, url in SOURCES.items():
        target = vendor / name
        if not target.exists():
            target.write_bytes(urllib.request.urlopen(url).read())
        hashes[name] = {'url': url, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    simd = vendor / 'x86-simd-sort'
    if not simd.exists():
        subprocess.run(['git', 'clone', 'https://github.com/numpy/x86-simd-sort.git', str(simd)], check=True)
        subprocess.run(['git', '-C', str(simd), 'checkout', SIMD_COMMIT], check=True)
    commit = subprocess.check_output(['git', '-C', str(simd), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != SIMD_COMMIT:
        raise RuntimeError('Unexpected SIMD commit; preserve reproducibility before continuing')
    hashes['x86-simd-sort'] = {'url': 'https://github.com/numpy/x86-simd-sort', 'commit': commit}
    highway = vendor / 'highway'
    if not highway.exists():
        subprocess.run(['git', 'clone', 'https://github.com/google/highway.git', str(highway)], check=True)
        subprocess.run(['git', '-C', str(highway), 'checkout', HIGHWAY_COMMIT], check=True)
    commit = subprocess.check_output(['git', '-C', str(highway), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError('Unexpected Highway commit')
    hashes['highway'] = {'url': 'https://github.com/google/highway', 'commit': commit, 'dispatch': 'VQSORT_ONLY_STATIC + HWY_COMPILE_ONLY_STATIC, march=native'}
    build = ROOT / 'build' / platform.system().lower()
    build.mkdir(parents=True, exist_ok=True)
    exe = build / 'bench.exe'
    flags = ['g++', '-O3', '-march=native', '-DNDEBUG', '-std=c++17', '-I'+str(simd / 'src'), '-I'+str(highway), str(ROOT / 'bench.cpp'), str(ROOT / 'vq_bridge.cpp'), str(highway / 'hwy' / 'abort.cc'), '-o', str(exe)]
    if platform.system() == 'Linux':
        for name, expected_commit in IPS_COMMITS.items():
            location = vendor / name
            if not location.exists():
                subprocess.run(['git', 'clone', '--recursive', f'https://github.com/ips4o/{name}.git', str(location)], check=True)
                subprocess.run(['git', '-C', str(location), 'checkout', expected_commit], check=True)
                subprocess.run(['git', '-C', str(location), 'submodule', 'update', '--init', '--recursive'], check=True)
            actual = subprocess.check_output(['git', '-C', str(location), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != expected_commit:
                raise RuntimeError(f'Unexpected {name} commit')
            hashes[name] = {'url': f'https://github.com/ips4o/{name}', 'commit': actual, 'api': 'sequential sort'}
            flags.append('-I'+str(location / 'include'))
        flags.extend(['-DSUPERSORT_WITH_IPS', str(ROOT / 'ips_bridge.cpp'), '-ltbb', '-latomic', '-pthread'])
    subprocess.run(flags, check=True)
    out = ROOT / 'results' / args.tag
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(ROOT / 'bench.cpp', out / 'bench.cpp')
    shutil.copy2(ROOT / 'vq_bridge.cpp', out / 'vq_bridge.cpp')
    shutil.copy2(ROOT / 'profile_predict.hpp', out / 'profile_predict.hpp')
    shutil.copy2(ROOT / 'ips_bridge.cpp', out / 'ips_bridge.cpp')
    shutil.copy2(Path(__file__), out / 'run.py')
    shutil.copytree(ROOT / 'include', out / 'include')
    (out / 'vendor').mkdir()
    for name in SOURCES:
        shutil.copy2(vendor / name, out / 'vendor' / name)
    meta = {'utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
            'compiler': subprocess.check_output(['g++', '--version'], text=True),
            'flags': flags, 'arguments': vars(args), 'vendor': hashes,
            'source_sha256': hashlib.sha256((ROOT / 'bench.cpp').read_bytes()).hexdigest(),
            'vq_bridge_sha256': hashlib.sha256((ROOT / 'vq_bridge.cpp').read_bytes()).hexdigest(),
            'header_sha256': {str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in (ROOT / 'include').rglob('*.hpp')},
            'logical_cpu': args.cpu,
            'timing': 'single-thread; allocation included; input copy and correctness excluded; one warmup per case; shuffled algorithm order'}
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    rows = []
    with (out / 'raw.csv').open('w', newline='') as f:
        writer = None
        for n in args.sizes:
            for dist in args.distributions:
                for seed in args.seeds:
                    print(f'Running n={n} distribution={dist} seed={seed}', flush=True)
                    command = [str(exe), str(n), str(args.repeats), dist, str(seed)]
                    if args.algorithms:
                        command.append(','.join(args.algorithms))
                    result = subprocess.run(command, text=True, capture_output=True, check=True)
                    if result.stderr:
                        (out / f'diagnostic-{n}-{dist}-{seed}.csv').write_text('n,src_mod4096,scratch_mod4096,allocate_us,scatter_us,sortcopy_us,free_us,overflow\n'+result.stderr, encoding='utf-8')
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
    if not args.quiet:
        print('\n'.join(lines))
    print(f'Saved {len(rows)} timed samples to {out}')

if __name__ == '__main__':
    main()
