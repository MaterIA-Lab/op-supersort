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
POWER_COMMIT = '1d078b6be9023e134c4f8f6de88e2406dc681e89'
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
    p.add_argument('--runs-diagnostic', action='store_true', help='Untimed E037 run/movement counts; extra exact checks')
    p.add_argument('--tree-diagnostic', action='store_true', help='Untimed E038 plan/merge counts; extra exact checks')
    p.add_argument('--cpu', type=int, help='Pin runner and inherited child processes to a logical CPU')
    args = p.parse_args()
    if min(args.sizes) < 0 or args.repeats < 1:
        p.error('sizes must be nonnegative; repeats must be positive')
    if args.runs_diagnostic and args.tree_diagnostic:
        p.error('Use one diagnostic format per run')
    if (args.runs_diagnostic or args.tree_diagnostic) and not args.algorithms:
        p.error('Diagnostics require explicit --algorithms')
    if (ROOT / 'results' / args.tag).exists():
        p.error('Result tag already exists; choose a new tag before compiling')
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
        power = vendor / 'powersort'
        if not power.exists():
            subprocess.run(['git', 'clone', 'https://github.com/sebawild2/powersort.git', str(power)], check=True)
            subprocess.run(['git', '-C', str(power), 'checkout', POWER_COMMIT], check=True)
        actual = subprocess.check_output(['git', '-C', str(power), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != POWER_COMMIT:
            raise RuntimeError('Unexpected Powersort commit')
        dirty = subprocess.check_output(['git', '-C', str(power), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
        if dirty:
            raise RuntimeError('Powersort tracked sources modified')
        hashes['powersort'] = {'url': 'https://github.com/sebawild2/powersort', 'commit': actual,
                              'api': 'fresh algorithms::powersort<uint32_t*>; defaults minRunLen24 COPY_BOTH; no persistent workspace'}
        flags.append(str(ROOT / 'power_bridge.cpp'))
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
    tracked = [ROOT / x for x in ['bench.cpp', 'vq_bridge.cpp', 'ips_bridge.cpp', 'power_bridge.cpp', 'profile_predict.hpp']]
    tracked.extend((ROOT / 'include').rglob('*.hpp'))
    source_hashes = {str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in tracked}
    subprocess.run(flags, check=True)
    if any(hashlib.sha256(x.read_bytes()).hexdigest() != source_hashes[str(x.relative_to(ROOT))] for x in tracked):
        raise RuntimeError('Sources changed during compilation; discard build and rerun with unchanged sources')
    out = ROOT / 'results' / args.tag
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(ROOT / 'bench.cpp', out / 'bench.cpp')
    shutil.copy2(ROOT / 'vq_bridge.cpp', out / 'vq_bridge.cpp')
    shutil.copy2(ROOT / 'profile_predict.hpp', out / 'profile_predict.hpp')
    shutil.copy2(ROOT / 'ips_bridge.cpp', out / 'ips_bridge.cpp')
    shutil.copy2(ROOT / 'power_bridge.cpp', out / 'power_bridge.cpp')
    shutil.copy2(Path(__file__), out / 'run.py')
    shutil.copytree(ROOT / 'include', out / 'include')
    (out / 'vendor').mkdir()
    if platform.system() == 'Linux':
        shutil.copytree(power / 'src', out / 'vendor' / 'powersort' / 'src')
        shutil.copy2(power / 'LICENSE', out / 'vendor' / 'powersort' / 'LICENSE')
        shutil.copy2(power / 'README.md', out / 'vendor' / 'powersort' / 'README.md')
    for name in SOURCES:
        shutil.copy2(vendor / name, out / 'vendor' / name)
    meta = {'utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
            'compiler': subprocess.check_output(['g++', '--version'], text=True),
            'flags': flags, 'arguments': vars(args), 'vendor': hashes,
            'source_sha256': hashlib.sha256((ROOT / 'bench.cpp').read_bytes()).hexdigest(),
            'source_files_sha256': source_hashes,
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
                    elif args.runs_diagnostic:
                        raise RuntimeError('--runs-diagnostic requires explicit --algorithms')
                    if args.runs_diagnostic:
                        command.append('runs_diagnostic')
                    if args.tree_diagnostic:
                        command.append('tree_diagnostic')
                    result = subprocess.run(command, text=True, capture_output=True, check=True)
                    if result.stderr:
                        diagnostic_header = ('mode,runs,simd_elements,reversed_elements,levels,merged_elements,copied_elements,final_elements\n' if args.runs_diagnostic else 'n,src_mod4096,scratch_mod4096,allocate_us,scatter_us,sortcopy_us,free_us,overflow\n')
                        if args.tree_diagnostic:
                            diagnostic_header='mode,runs,run_hash,simd_elements,reversed_elements,operations,tree_elements,executed_elements,copied_elements,skipped\n'
                        (out / f'diagnostic-{n}-{dist}-{seed}.csv').write_text(diagnostic_header+result.stderr, encoding='utf-8')
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
