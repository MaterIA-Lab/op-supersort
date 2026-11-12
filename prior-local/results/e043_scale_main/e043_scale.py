"""Preregistered serial scale matrix using the archived E040 executable."""
import csv
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
REGISTRATION = ROOT / 'notes/E043 - Prerregistro escala.md'
ORIGIN = ROOT / 'results/e040_quick_holdout_linux'
ENVIRONMENT = ROOT / 'results/e043_environment'
RUNS = [
    ('e043_scale_main', 3000, ['--sizes', '100000', '1000000', '10000000',
        '--seeds', '60101', '73529', '--repeats', '5', '--distributions',
        'uniform', 'splitmix', 'sorted', 'reverse', 'equal', 'few',
        'near_sorted', 'alternating', 'skew', 'forced_middle']),
    ('e043_scale_100m', 63, ['--sizes', '100000000', '--seeds', '91573',
        '--repeats', '3', '--distributions', 'uniform', 'few', 'forced_middle',
        '--algorithms', 'pdq', 'simd', 'vq', 'ips2ra', 'ips4o', 'simd256dso', 'quick128']),
]


def probe_environment():
    ENVIRONMENT.mkdir(exist_ok=False)
    shutil.copy2(__file__, ENVIRONMENT / 'e043_scale.py')
    shutil.copy2(REGISTRATION, ENVIRONMENT / 'preregistration.md')
    probe = ['taskset', '-c', '2', 'perf', 'stat', '-e',
             'cycles,instructions,cache-misses,branch-misses', '--', 'true']
    if shutil.which('perf'):
        result = subprocess.run(probe, text=True, capture_output=True)
        pmu = {'command': probe, 'returncode': result.returncode,
               'stdout': result.stdout, 'stderr': result.stderr}
    else:
        pmu = {'available': False, 'reason': 'perf unavailable'}
    with (ENVIRONMENT / 'environment.json').open('x', encoding='utf-8') as stream:
        json.dump({'utc': datetime.now(timezone.utc).isoformat(),
                   'meminfo': Path('/proc/meminfo').read_text(),
                   'perf_event_paranoid': Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip(),
                   'pmu_probe': pmu}, stream, indent=2)


def analyze(folder, planned_samples):
    with (folder / 'raw.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != planned_samples:
        raise RuntimeError('Unexpected sample count')
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        case = (int(row['n']), row['distribution'], int(row['seed']))
        groups[case][row['algorithm']].append(float(row['ms']))
    lines = ['# E043 — quick128 a escala', '',
             'Ratio >1 favorece quick128. Las referencias son las de esta tanda. '
             'RSS máximo corresponde al proceso completo con todos los algoritmos. '
             'El CSV y summary.md conservan las mediciones de todos los algoritmos.', '',
             '| n | distribución | semilla | quick128 mediana ms | quick128 min–max ms | DSO256/quick | host/quick | mejor referencia | mejor/quick | RSS pico MiB |',
             '|---:|---|---:|---:|---:|---:|---:|---|---:|---:|']
    wins = defaultdict(list)
    for (n, distribution, seed), timings in sorted(groups.items()):
        median = {algorithm: statistics.median(samples) for algorithm, samples in timings.items()}
        quick = median['quick128']
        best = min((a for a in median if a != 'quick128'), key=median.__getitem__)
        ratios = [median[a] / quick for a in ('simd256dso', 'simd', best)]
        wins[n].append(ratios)
        path = folder / f'process-{n}-{distribution}-{seed}.txt'
        resources = dict(line.split('=', 1) for line in path.read_text().splitlines())
        samples = timings['quick128']
        lines.append(f'| {n} | {distribution} | {seed} | {quick:.6f} | '
                     f'{min(samples):.6f}–{max(samples):.6f} | {ratios[0]:.3f} | '
                     f'{ratios[1]:.3f} | {best} | {ratios[2]:.3f} | '
                     f'{int(resources["max_rss_kib"])/1024:.1f} |')
    lines += ['', '| n | entradas nominales | gana DSO256 | gana host | gana mejor referencia |',
              '|---:|---:|---:|---:|---:|']
    for n, comparisons in sorted(wins.items()):
        counts = [sum(ratios[i] > 1 for ratios in comparisons) for i in range(3)]
        lines.append(f'| {n} | {len(comparisons)} | {counts[0]} | {counts[1]} | {counts[2]} |')
    lines += ['', f'{len(rows)} muestras y {len(rows) + sum(map(len, groups.values()))} '
              'salidas exactas con calentamientos.']
    with (folder / 'analysis-scale.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
    shutil.copy2(__file__, folder / 'e043_scale.py')
    shutil.copy2(ENVIRONMENT / 'environment.json', folder / 'environment-scale.json')
    print('\n'.join(lines[-8:]), flush=True)


def main():
    probe_environment()
    for tag, planned_samples, arguments in RUNS:
        subprocess.run([sys.executable, str(ROOT / 'run_existing.py'),
                        '--from-run', str(ORIGIN), '--tag', tag,
                        '--registration', str(REGISTRATION), '--process-memory',
                        *arguments], check=True)
        analyze(ROOT / 'results' / tag, planned_samples)


if __name__ == '__main__':
    main()
