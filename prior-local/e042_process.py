"""E042-B: fixed repeated-process diagnostic on the unmodified E040 binary.

Run only after E042-A compilation/sanitizers finish. This script never builds,
changes a performance source, or retries a failed process. All outputs are new.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import time
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
ORIGIN = ROOT / 'results' / 'e040_quick_holdout_linux'
OUT = ROOT / 'results' / 'e042_process_variation'
PREREG = ROOT / 'notes' / 'E042 - Prerregistro trabajo y procesos.md'
CASES = [
    (8193, 'skew', 33013),
    (8193, 'uniform', 33013),
    (180013, 'splitmix', 14009),
    (180013, 'few', 58013),
    (8209, 'forced_middle', 58013),
    (8209, 'forced_tail', 41011),
    (8209, 'forced_front', 58013),
    (180013, 'uniform', 41011),
    (1500007, 'splitmix', 58013),
    (180013, 'equal', 14009),
    (180013, 'sorted', 14009),
    (180013, 'alternating', 14009),
]
ALGORITHMS = ['std', 'stdstable', 'pdq', 'simd', 'vq', 'power', 'ips2ra',
              'ips4o', 'simd256dso', 'quick128']
BATCHES = 8
REPEATS = 31
RANDOM_SEED = 420042
PARENT_CPU = 0
CHILD_CPU = 2
MAP_LIMIT_SECONDS = .25


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(path):
    path = Path(path)
    return {p.relative_to(path).as_posix(): sha(p)
            for p in sorted(path.rglob('*')) if p.is_file()}


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def maybe_read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return {'unavailable': type(error).__name__, 'message': str(error)}


def environment():
    paths = [
        '/proc/sys/kernel/randomize_va_space',
        '/proc/sys/kernel/perf_event_paranoid',
        '/proc/sys/kernel/osrelease',
        '/proc/sys/kernel/sched_autogroup_enabled',
        '/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor',
        '/sys/devices/system/cpu/cpu2/cpufreq/scaling_cur_freq',
        '/sys/devices/system/cpu/cpu2/cpufreq/cpuinfo_min_freq',
        '/sys/devices/system/cpu/cpu2/cpufreq/cpuinfo_max_freq',
    ]
    return {'utc': utc(), 'platform': platform.platform(),
            'python': platform.python_version(), 'parent_pid': os.getpid(),
            'parent_affinity': sorted(os.sched_getaffinity(0)),
            'child_affinity_requested': [CHILD_CPU],
            'exposed_system_values': {path: maybe_read(path) for path in paths},
            'cpuinfo': maybe_read('/proc/cpuinfo'),
            'loadavg': maybe_read('/proc/loadavg')}


def verify_origin(old, assembly):
    if platform.platform() != old['platform']:
        raise RuntimeError('Environment differs from the E040 recorded platform')
    if old['logical_cpu'] != CHILD_CPU:
        raise RuntimeError('E040 did not use the preregistered logical CPU')
    if old['arguments']['algorithms'] != ALGORITHMS:
        raise RuntimeError('The archived algorithm order differs from E042')
    expected_binary = assembly['host_binary_sha256']
    if sha(ORIGIN / 'bench.bin') != expected_binary:
        raise RuntimeError('Archived E040 executable hash mismatch')
    for name, wanted in old['source_files_sha256'].items():
        if sha(ORIGIN / name) != wanted:
            raise RuntimeError('E040 source snapshot hash mismatch: ' + name)
    quick = old['quick_threshold']
    for threshold, variant in quick['variants'].items():
        library = quick['libraries'][threshold]
        if sha(library) != variant['library_sha256']:
            raise RuntimeError('Original linked DSO changed: ' + library)
        if sha(ORIGIN / 'quick' / Path(library).name) != variant['library_sha256']:
            raise RuntimeError('Archived DSO changed: ' + library)
        source = ORIGIN / 'quick' / ('src' + threshold)
        if tree_hashes(source) != variant['source_sha256_after']:
            raise RuntimeError('Archived private source tree changed: ' + threshold)
    return {'binary_sha256': expected_binary,
            'linked_dso_sha256': {quick['libraries'][threshold]:
                                 variant['library_sha256']
                                 for threshold, variant in quick['variants'].items()}}


def capture_maps(pid, exe, libraries, destination):
    """Read the first map with the original executable and both DSOs loaded.

    Do not wait/reap here: os.wait4 below owns the child's lifetime. A zombie's
    empty/missing maps are a recorded unsuccessful capture, never a retry.
    """
    started = time.monotonic()
    deadline = started + MAP_LIMIT_SECONDS
    wanted = [str(exe), *map(str, libraries)]
    attempts = 0
    ready = False
    last = ''
    error = None
    while True:
        attempts += 1
        try:
            last = Path(f'/proc/{pid}/maps').read_text()
        except OSError as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
            break
        if all(name in last for name in wanted):
            ready = True
            break
        if not last or time.monotonic() >= deadline:
            break
        time.sleep(.002)
    with destination.open('x', encoding='utf-8') as stream:
        stream.write(last)
    return {'ready': ready, 'attempts': attempts,
            'elapsed_seconds': time.monotonic() - started,
            'limit_seconds': MAP_LIMIT_SECONDS, 'error': error,
            'required_mappings': wanted,
            'process_status_at_capture': maybe_read(f'/proc/{pid}/status'),
            'map_file': str(destination.relative_to(OUT))}


def run_process(command, prefix, libraries):
    stdout_path = prefix.with_suffix('.stdout.csv')
    stderr_path = prefix.with_suffix('.stderr.txt')
    stdout_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    stderr_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    started_utc = utc()
    started = time.monotonic()
    try:
        pid = os.fork()
    except BaseException:
        os.close(stdout_fd)
        os.close(stderr_fd)
        raise
    if pid == 0:
        try:
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
            stdin_fd = os.open('/dev/null', os.O_RDONLY)
            os.dup2(stdin_fd, 0)
            os.close(stdin_fd)
            os.execvp(command[0], command)
        except BaseException as error:
            os.write(2, (repr(error) + '\n').encode('utf-8', errors='replace'))
            os._exit(127)
    os.close(stdout_fd)
    os.close(stderr_fd)
    observation_error = None
    try:
        maps = capture_maps(pid, ORIGIN / 'bench.bin', libraries,
                            prefix.with_suffix('.maps.txt'))
    except Exception as error:
        # Even an observer I/O failure must not abandon the explicitly started
        # native process. Reap it before reporting the failed observation.
        observation_error = error
        maps = {'ready': False, 'error': repr(error)}
    while True:
        try:
            waited, status, usage = os.wait4(pid, 0)
            break
        except InterruptedError:
            continue
    if waited != pid:
        raise RuntimeError('wait4 returned an unexpected child')
    result = {
        'pid': pid, 'started_utc': started_utc, 'finished_utc': utc(),
        'exit_code': os.waitstatus_to_exitcode(status),
        'elapsed_seconds_whole_process': time.monotonic() - started,
        'rusage_scope': 'whole child: taskset, generation, warmup, sort, validation, output',
        'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
        'max_rss_kib_linux': usage.ru_maxrss,
        'minor_faults': usage.ru_minflt, 'major_faults': usage.ru_majflt,
        'voluntary_context_switches': usage.ru_nvcsw,
        'involuntary_context_switches': usage.ru_nivcsw,
        'maps': maps, 'command': command,
        'stdout': str(stdout_path.relative_to(OUT)),
        'stderr': str(stderr_path.relative_to(OUT)),
    }
    write_json(prefix.with_suffix('.json'), result)
    if observation_error is not None:
        raise RuntimeError('Map observer failed; native child was reaped') from observation_error
    if result['exit_code'] != 0:
        raise RuntimeError(f'Process failed without retry; inspect {prefix}.json')
    with stdout_path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    n, distribution, seed = int(command[4]), command[6], int(command[7])
    if len(rows) != REPEATS * len(ALGORITHMS):
        raise RuntimeError('Unexpected row count; evidence retained without retry')
    groups = {}
    for row in rows:
        if list(row) != ['n', 'distribution', 'seed', 'repeat', 'algorithm', 'ms']:
            raise RuntimeError('Native CSV schema changed')
        if (int(row['n']), row['distribution'], int(row['seed'])) != (n, distribution, seed):
            raise RuntimeError('Native CSV case differs from command')
        if not math.isfinite(float(row['ms'])) or float(row['ms']) < 0:
            raise RuntimeError('Invalid measured time')
        groups.setdefault(int(row['repeat']), []).append(row['algorithm'])
    if sorted(groups) != list(range(REPEATS)) or any(
            sorted(names) != sorted(ALGORITHMS) for names in groups.values()):
        raise RuntimeError('Native CSV does not contain every algorithm per round')
    return rows, result


def analyze(rows, processes):
    groups = {}
    for row in rows:
        key = (int(row['n']), row['distribution'], int(row['seed']),
               int(row['process_batch']), row['algorithm'])
        groups.setdefault(key, []).append(row)
    medians = {}
    median_rows = []
    for key, records in sorted(groups.items()):
        n, distribution, seed, batch, algorithm = key
        blocks = {'all': records,
                  '0-14': [r for r in records if int(r['repeat']) < 15],
                  '15-30': [r for r in records if int(r['repeat']) >= 15]}
        for block, values in blocks.items():
            samples = [float(r['ms']) for r in values]
            value = statistics.median(samples)
            medians[(*key, block)] = value
            median_rows.append({'n': n, 'distribution': distribution, 'seed': seed,
                                'process_batch': batch, 'algorithm': algorithm,
                                'round_block': block, 'samples': len(samples),
                                'median_ms': value, 'min_ms': min(samples),
                                'max_ms': max(samples)})
    with (OUT / 'process-medians.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=median_rows[0].keys())
        writer.writeheader()
        writer.writerows(median_rows)
    summary = [
        '# E042-B — variación entre procesos', '',
        'Diagnóstico prefijado, sin promoción de candidato. Ejecutable y DSOs E040 '
        'verificados antes/después; salidas exactas contra std::sort en cada llamada. '
        'Ocho procesos por entrada, 31 rondas medidas y un calentamiento por algoritmo. '
        'Reutilización deliberada de fallos y controles: no es un holdout independiente.', '',
        'Ratio >1 favorece quick128. Rangos entre las ocho medianas por proceso. '
        'No se mezclan rondas como datasets independientes. La captura de mapas puede '
        'perturbar; direcciones y rusage no identifican una causa de las diferencias.', '',
        '| n | distribución | semilla | quick128 mediana ms, rango | '
        'DSO256/quick128, rango | victorias /8 | host/quick128, rango | victorias /8 |',
        '|---:|---|---:|---:|---:|---:|---:|---:|',
    ]
    details = [
        '# E042-B — todas las medianas y bloques', '',
        'Ratio >1 favorece quick128. Bloques prefijados: rondas0–14 y15–30. '
        'No elegir el bloque favorable ni borrar negativos anteriores. '
        'Los diez algoritmos completos están en process-medians.csv.', '',
        '| n | distribución | semilla | tanda | quick ms | DSO/quick | host/quick | '
        'DSO/quick 0–14 | DSO/quick 15–30 | host/quick 0–14 | host/quick 15–30 |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for case in CASES:
        n, distribution, seed = case
        quick_values, control_ratios, host_ratios = [], [], []
        for batch in range(BATCHES):
            def value(algorithm, block='all'):
                return medians[(*case, batch, algorithm, block)]
            quick = value('quick128')
            control = value('simd256dso') / quick
            host = value('simd') / quick
            quick_values.append(quick)
            control_ratios.append(control)
            host_ratios.append(host)
            blocks = [value(algorithm, block) / value('quick128', block)
                      for algorithm in ['simd256dso', 'simd']
                      for block in ['0-14', '15-30']]
            details.append(f'| {n} | {distribution} | {seed} | {batch} | {quick:.6f} | '
                           f'{control:.6f} | {host:.6f} | ' +
                           ' | '.join(f'{ratio:.6f}' for ratio in blocks) + ' |')
        def span(values, digits=6):
            return f'{min(values):.{digits}f}–{max(values):.{digits}f}'
        summary.append(f'| {n} | {distribution} | {seed} | {span(quick_values)} | '
                       f'{span(control_ratios)} | {sum(x > 1 for x in control_ratios)} | '
                       f'{span(host_ratios)} | {sum(x > 1 for x in host_ratios)} |')
    captures = sum(p['maps']['ready'] for p in processes)
    summary += ['', f'{len(rows)} muestras medidas; '
                f'{len(rows) + len(processes) * len(ALGORITHMS)} salidas exactas '
                f'incluyendo calentamientos. Mapas completos tempranos: {captures}/{len(processes)}.',
                '', 'RSS máximo, page faults y cambios de contexto corresponden al proceso '
                'completo, incluida generación y verificación; no son contadores de la región '
                'de ordenación. Frecuencia/carga no controladas. No se atribuye causalidad '
                'a ASLR, caché, asignador o frecuencia.', '',
                '[Todas las medianas por proceso y ambos bloques](analysis-process.md).']
    with (OUT / 'analysis-process.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(details) + '\n')
    # The index recognizes summary.md as completion; create it last in main.
    return '\n'.join(summary) + '\n'


def main():
    if platform.system() != 'Linux' or not hasattr(os, 'wait4'):
        raise RuntimeError('E042-B requires the original Linux environment and wait4')
    if OUT.exists():
        raise FileExistsError(OUT)
    old = json.loads((ORIGIN / 'metadata.json').read_text())
    assembly = json.loads((ORIGIN / 'quick-assembly.json').read_text())
    original_integrity = verify_origin(old, assembly)
    source_integrity = {'e042_process.py': sha(__file__),
                        'preregistration.md': sha(PREREG)}
    available = os.sched_getaffinity(0)
    if not {PARENT_CPU, CHILD_CPU}.issubset(available):
        raise RuntimeError('Required observer/child CPUs are unavailable')
    if shutil.which('taskset') is None:
        raise RuntimeError('taskset unavailable')
    os.sched_setaffinity(0, {PARENT_CPU})
    OUT.mkdir()
    # Preserve complete evidence in a nested archive, keeping every original
    # raw.csv/summary.md intact and separate from this diagnostic's new files.
    shutil.copytree(ORIGIN, OUT / 'origin')
    original_tree = tree_hashes(ORIGIN)
    if tree_hashes(OUT / 'origin') != original_tree:
        raise RuntimeError('Complete origin archive differs after copying')
    shutil.copy2(__file__, OUT / 'e042_process.py')
    shutil.copy2(PREREG, OUT / 'preregistration.md')
    (OUT / 'processes').mkdir()
    rng = random.Random(RANDOM_SEED)
    schedule = []
    for batch in range(BATCHES):
        cases = list(CASES)
        rng.shuffle(cases)
        schedule.extend({'process_batch': batch, 'process_order': order,
                         'n': n, 'distribution': distribution, 'seed': seed}
                        for order, (n, distribution, seed) in enumerate(cases))
    metadata = {
        'stage': 'E042-B repeated-process diagnostic, not an independent holdout',
        'utc': utc(), 'platform': platform.platform(), 'logical_cpu': CHILD_CPU,
        'observer_logical_cpu': PARENT_CPU, 'compilation': 'NONE',
        'reused_executable': str(ORIGIN / 'bench.bin'),
        'reused_from': str(ORIGIN), 'original_integrity': original_integrity,
        'origin_tree_sha256': original_tree, 'source_sha256': source_integrity,
        'arguments': {'algorithms': ALGORITHMS, 'repeats': REPEATS,
                      'process_batches': BATCHES, 'cases': CASES,
                      'shuffle_seed': RANDOM_SEED},
        'schedule': schedule, 'environment_before': environment(),
        'planned_measured_samples': BATCHES * len(CASES) * REPEATS * len(ALGORITHMS),
        'planned_exact_outputs': BATCHES * len(CASES) * (REPEATS + 1) * len(ALGORITHMS),
        'timing': old['timing'],
        'observer': 'early /proc/PID/maps polling on CPU0, <=0.25s; '
                    'taskset child CPU2; wait4 whole-process rusage; no retries',
    }
    write_json(OUT / 'metadata.json', metadata)
    all_rows, processes = [], []
    fields = ['process_batch', 'process_order', 'process_id',
              'n', 'distribution', 'seed', 'repeat', 'algorithm', 'ms']
    libraries = list(old['quick_threshold']['libraries'].values())
    with (OUT / 'raw.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        stream.flush()
        for planned in schedule:
            batch, order = planned['process_batch'], planned['process_order']
            n, distribution, seed = planned['n'], planned['distribution'], planned['seed']
            print(f'E042-B batch={batch} order={order} n={n} distribution={distribution} seed={seed}', flush=True)
            name = f'b{batch:02d}-o{order:02d}-{n}-{distribution}-{seed}'
            prefix = OUT / 'processes' / name
            command = ['taskset', '-c', str(CHILD_CPU), str(ORIGIN / 'bench.bin'),
                       str(n), str(REPEATS), distribution, str(seed), ','.join(ALGORITHMS)]
            rows, result = run_process(command, prefix, libraries)
            result.update(planned)
            processes.append(result)
            for row in rows:
                augmented = {'process_batch': batch, 'process_order': order,
                             'process_id': result['pid'], **row}
                writer.writerow(augmented)
                all_rows.append(augmented)
            stream.flush()
    if len(all_rows) != metadata['planned_measured_samples']:
        raise RuntimeError('Completed sample count differs from registration')
    after_integrity = verify_origin(old, assembly)
    if original_integrity != after_integrity or tree_hashes(ORIGIN) != original_tree:
        raise RuntimeError('Original evidence changed during execution')
    if tree_hashes(OUT / 'origin') != original_tree:
        raise RuntimeError('Retained origin archive changed during execution')
    if sha(__file__) != source_integrity['e042_process.py'] or sha(PREREG) != source_integrity['preregistration.md']:
        raise RuntimeError('Diagnostic script or preregistration changed during execution')
    if sha(OUT / 'e042_process.py') != source_integrity['e042_process.py'] or sha(OUT / 'preregistration.md') != source_integrity['preregistration.md']:
        raise RuntimeError('Retained diagnostic evidence changed during execution')
    summary = analyze(all_rows, processes)
    write_json(OUT / 'completion.json', {
        'utc': utc(), 'process_count': len(processes),
        'measured_samples': len(all_rows),
        'exact_outputs_including_warmup': len(all_rows) + len(processes) * len(ALGORITHMS),
        'warmup_output_count': len(processes) * len(ALGORITHMS),
        'maps_ready_count': sum(p['maps']['ready'] for p in processes),
        'integrity_after': after_integrity, 'environment_after': environment(),
        'processes': processes,
    })
    with (OUT / 'summary.md').open('x', encoding='utf-8') as stream:
        stream.write(summary)
    print(f'Saved {len(all_rows)} samples and {len(processes)} complete processes to {OUT}', flush=True)


if __name__ == '__main__':
    main()
