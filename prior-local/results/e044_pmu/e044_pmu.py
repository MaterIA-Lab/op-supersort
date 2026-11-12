"""Serial E044 counters around calls to the exact E040 shared libraries."""
import csv
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess

from e042_process import verify_origin, sha

ROOT = Path(__file__).resolve().parent
ORIGIN = ROOT / 'results/e040_quick_holdout_linux'
OUT = ROOT / 'results/e044_pmu'
CASES = [(8193, 'skew', 33013), (8209, 'forced_middle', 58013),
         (180013, 'splitmix', 14009), (180013, 'few', 58013), (180013, 'equal', 14009),
         (10000000, 'uniform', 60101), (10000000, 'few', 73529),
         (10000000, 'forced_middle', 60101)]
EVENTS = ('cycles', 'instructions', 'cache_misses', 'branch_misses')


def active(row):
    enabled = int(row['enabled_ns'])
    running = int(row['running_ns'])
    return 0 < running <= enabled and 100 * running >= 99 * enabled


def analyze(rows):
    groups = defaultdict(list)
    for row in rows:
        key = (int(row['n']), row['distribution'], int(row['seed']), row['algorithm'])
        groups[key].append(row)
    lines = ['# E044 — contadores por llamada', '',
             'Medianas crudas, sin restar el control vacío. Eventos genéricos WSL. '
             'La copia común y std::sort de verificación están fuera de la región contada.', '',
             '| n | distribución | semilla | algoritmo | ciclos | instrucciones | cache-misses | branch-misses | filas activas ≥99% |',
             '|---:|---|---:|---|---:|---:|---:|---:|---:|']
    for case in CASES:
        for algorithm in ('empty', 'simd256dso', 'quick128'):
            samples = groups[(*case, algorithm)]
            accepted = sum(map(active, samples))
            counts = [str(int(statistics.median(int(row[event]) for row in samples))) for event in EVENTS]
            if accepted != len(samples):
                counts = ['—'] * len(EVENTS)
            lines.append('| ' + ' | '.join([*map(str, case), algorithm, *counts,
                          f'{accepted}/{len(samples)}']) + ' |')
    lines += ['', '176 llamadas medidas y 192 salidas exactas con calentamientos. '
              '88 controles vacíos. Las filas con multiplexación se conservan en raw.csv. '
              'Los misses no se convierten en bytes DRAM ni establecen causalidad.']
    with (OUT / 'analysis.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
    print('\n'.join(lines), flush=True)


def main():
    old = json.loads((ORIGIN / 'metadata.json').read_text())
    assembly = json.loads((ORIGIN / 'quick-assembly.json').read_text())
    original_integrity = verify_origin(old, assembly)
    os.sched_setaffinity(0, {2})
    OUT.mkdir(exist_ok=False)
    for name in ('e044_pmu.py', 'e044_pmu.cpp', 'e042_process.py'):
        shutil.copy2(ROOT / name, OUT / name)
    shutil.copy2(ROOT / 'notes/E044 - Prerregistro contadores.md', OUT / 'preregistration.md')
    bench = (ORIGIN / 'bench.cpp').read_bytes()
    generator = bench[bench.index(b'V generate('):bench.index(b'int main(')]
    (OUT / 'e042_generator.inc').write_bytes(generator)
    known_generator = ROOT / 'results/e042_work_diagnostic/e042_generator.inc'
    if sha(OUT / 'e042_generator.inc') != sha(known_generator):
        raise RuntimeError('Generator differs from E042 and E040')
    libraries = [old['quick_threshold']['libraries'][name] for name in ('256', '128')]
    retained = OUT / 'libraries'
    retained.mkdir()
    for library in libraries:
        shutil.copy2(library, retained / Path(library).name)
    shutil.copytree(ORIGIN / 'quick/licenses', OUT / 'licenses')
    flags = ['g++', '-O3', '-DNDEBUG', '-march=native', '-std=c++17', str(OUT / 'e044_pmu.cpp'),
             *libraries, '-Wl,-rpath,' + str(Path(libraries[0]).parent), '-o', str(OUT / 'pmu.bin')]
    frozen = {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}
    compile_result = subprocess.run(flags, text=True, capture_output=True)
    (OUT / 'compile.log').write_text(compile_result.stdout + compile_result.stderr)
    compile_result.check_returncode()
    resolved = subprocess.check_output(['ldd', str(OUT / 'pmu.bin')], text=True)
    (OUT / 'linked-libraries.txt').write_text(resolved)
    if any(library not in resolved for library in libraries):
        raise RuntimeError('Unexpected runtime library resolution')
    metadata = {'utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
                'logical_cpu': 2, 'cases': CASES, 'flags': flags,
                'compiler': subprocess.check_output(['g++', '--version'], text=True),
                'source_sha256': frozen, 'binary_sha256': sha(OUT / 'pmu.bin'),
                'e040_integrity': original_integrity,
                'perf_event_paranoid': Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip(),
                'region': 'calling thread user mode; enable before DSO call and disable after return'}
    with (OUT / 'metadata.json').open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    rows = []
    with (OUT / 'raw.csv').open('x', newline='') as stream:
        writer = None
        for n, distribution, seed in CASES:
            print(f'E044 n={n} {distribution} {seed}', flush=True)
            command = [str(OUT / 'pmu.bin'), str(n), distribution, str(seed)]
            stem = f'{n}-{distribution}-{seed}'
            stdout_path = OUT / f'process-{stem}.stdout.csv'
            stderr_path = OUT / f'process-{stem}.stderr.txt'
            with stdout_path.open('x') as stdout, stderr_path.open('x') as stderr:
                result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=120)
            result.check_returncode()
            with stdout_path.open(newline='') as stdout:
                batch = list(csv.DictReader(stdout))
            keys = {(row['algorithm'], int(row['repeat'])) for row in batch}
            expected = {(algorithm, i) for algorithm in ('empty', 'simd256dso', 'quick128') for i in range(11)}
            if keys != expected or len(batch) != 33:
                raise RuntimeError('Incomplete counter CSV')
            if writer is None:
                writer = csv.DictWriter(stream, fieldnames=batch[0].keys())
                writer.writeheader()
            writer.writerows(batch)
            stream.flush()
            rows.extend(batch)
    if verify_origin(old, assembly) != original_integrity:
        raise RuntimeError('E040 files changed')
    if any(sha(OUT / name) != want for name, want in frozen.items()) or sha(OUT / 'pmu.bin') != metadata['binary_sha256']:
        raise RuntimeError('Diagnostic source or executable changed')
    analyze(rows)


if __name__ == '__main__':
    main()
