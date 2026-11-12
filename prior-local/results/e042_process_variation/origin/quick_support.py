"""E040 isolated AVX2 sorter DSOs; importing this module performs no builds.

prepare(root, build, tag, sanitize=False) creates an exclusive build/quick_<tag>
directory and builds the control then candidate, serially. Its result is JSON
serializable; append info['link_flags'] when linking the host executable.
archive(info, out) exclusively copies all retained evidence into out/quick.
"""
from pathlib import Path
import hashlib
import json
import platform
import re
import shutil
import subprocess

SIMD_COMMIT = '6e059b14975df2e3c74260ec905167a1be5a34ca'
HEADER = 'avx2-32bit-qsort.hpp'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tree_hashes(directory):
    directory = Path(directory)
    return {p.relative_to(directory).as_posix(): _sha(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


def _capture(command):
    return subprocess.check_output(command, text=True).strip()


def _modify_uint32_threshold(path):
    """Replace one exact byte span; preserve all other bytes and line endings."""
    path = Path(path)
    original = path.read_bytes()
    marker = b'struct avx2_vector<uint32_t> {'
    old = b'static constexpr int network_sort_threshold = 256;'
    new = b'static constexpr int network_sort_threshold = 128;'
    if original.count(marker) != 1:
        raise RuntimeError('Expected one uint32 AVX2 specialization')
    start = original.index(marker)
    end = original.find(b'\n};', start)
    if end < 0:
        raise RuntimeError('Cannot locate end of uint32 AVX2 specialization')
    body = original[start:end]
    if body.count(old) != 1:
        raise RuntimeError('Expected exactly one uint32 threshold256 declaration')
    offset = start + body.index(old)
    modified = original[:offset] + new + original[offset + len(old):]
    assert len(modified) == len(original)
    assert modified[:offset] == original[:offset]
    assert modified[offset + len(old):] == original[offset + len(old):]
    path.write_bytes(modified)
    return {'file': HEADER, 'byte_offset': offset,
            'before': old.decode('ascii'), 'after': new.decode('ascii'),
            'replacement_count': 1, 'line_endings_preserved': True,
            'sha256_before': hashlib.sha256(original).hexdigest(),
            'sha256_after': hashlib.sha256(modified).hexdigest()}


def _defined_dynamic_exports(readelf_text):
    exports = []
    for line in readelf_text.splitlines():
        columns = line.split()
        if (len(columns) >= 8 and columns[0].endswith(':')
                and columns[4] in {'GLOBAL', 'WEAK', 'UNIQUE'}
                and columns[6] != 'UND'
                and columns[5] in {'DEFAULT', 'PROTECTED'}):
            exports.append(columns[7].split('@', 1)[0])
    return sorted(set(exports))


def prepare(root, build, tag, sanitize=False):
    if platform.system() != 'Linux':
        raise RuntimeError('E040 DSOs require the preregistered Linux environment')
    if not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', tag):
        raise ValueError('Use a simple, nonempty result tag')
    root = Path(root).resolve()
    build = Path(build).resolve()
    repo = root / 'vendor' / 'x86-simd-sort'
    commit = _capture(['git', '-C', str(repo), 'rev-parse', 'HEAD'])
    if commit != SIMD_COMMIT:
        raise RuntimeError('Unexpected x86-simd-sort source commit')
    dirty = _capture(['git', '-C', str(repo), 'status', '--porcelain',
                      '--untracked-files=no'])
    if dirty:
        raise RuntimeError('Original tracked x86-simd-sort sources are modified')
    original_hashes = _tree_hashes(repo / 'src')
    build.mkdir(parents=True, exist_ok=True)
    work = build / ('quick_' + tag)
    work.mkdir(exist_ok=False)
    for threshold in (256, 128):
        shutil.copytree(repo / 'src', work / ('src' + str(threshold)))
    delta = _modify_uint32_threshold(work / 'src128' / HEADER)
    control_hashes = _tree_hashes(work / 'src256')
    candidate_hashes = _tree_hashes(work / 'src128')
    if control_hashes != original_hashes:
        raise RuntimeError('Control source copy differs from original')
    changed = sorted(k for k in set(control_hashes) | set(candidate_hashes)
                     if control_hashes.get(k) != candidate_hashes.get(k))
    if changed != [HEADER]:
        raise RuntimeError('Candidate differs outside the one permitted header')
    if (delta['sha256_before'] != original_hashes[HEADER]
            or delta['sha256_after'] != candidate_hashes[HEADER]):
        raise RuntimeError('Threshold delta does not describe copied source')
    shutil.copy2(root / 'quick_bridge.cpp', work / 'quick_bridge.cpp')
    shutil.copy2(Path(__file__), work / 'quick_support.py')
    licenses = sorted(p for p in repo.iterdir() if p.is_file()
                      and p.name.lower().startswith(('license', 'copying', 'notice')))
    if not licenses:
        raise RuntimeError('No upstream license found; retain evidence and stop')
    (work / 'licenses').mkdir()
    for src in licenses:
        shutil.copy2(src, work / 'licenses' / src.name)
    license_hashes = _tree_hashes(work / 'licenses')
    optimization = (['-O1', '-g', '-fsanitize=address,undefined',
                     '-fno-omit-frame-pointer'] if sanitize
                    else ['-O3', '-DNDEBUG'])
    common = ['g++', *optimization, '-march=native', '-std=c++17', '-shared',
              '-fPIC', '-fvisibility=hidden', '-Wl,-Bsymbolic']
    info = {'source_commit': commit, 'source_url': 'https://github.com/numpy/x86-simd-sort',
            'root': str(root), 'work_dir': str(work), 'stage_dir': str(work), 'tag': tag,
            'sanitize': bool(sanitize), 'common_flags': common,
            'compiler': _capture(['g++', '--version']),
            'source_sha256_original': original_hashes,
            'delta': delta, 'license_sha256': license_hashes, 'variants': {}}
    # Await each complete native build before starting the next one. The caller
    # must also keep all benchmark processes stopped while prepare() is active.
    for threshold in (256, 128):
        name = str(threshold)
        api = 'ss_xss' + name
        src = work / ('src' + name)
        library = work / ('libss_xss' + name + '.so')
        version_map = work / ('exports' + name + '.map')
        version_map.write_text('{\n  global: ' + api + ';\n  local: *;\n};\n',
                               encoding='ascii')
        before = _tree_hashes(src)
        auxiliary_before = {p.name: _sha(p) for p in
                            [work / 'quick_bridge.cpp', work / 'quick_support.py', version_map]}
        command = [*common, '-DSORT_API=' + api,
                   '-DEXPECTED_THRESHOLD=' + name, '-I' + str(src),
                   str(work / 'quick_bridge.cpp'),
                   '-Wl,--version-script=' + str(version_map),
                   '-Wl,-soname,' + library.name, '-o', str(library)]
        result = subprocess.run(command, text=True, capture_output=True)
        log = work / ('compile' + name + '.log')
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'DSO {api} compilation failed; evidence retained in {log}')
        after = _tree_hashes(src)
        auxiliary_after = {p.name: _sha(p) for p in
                           [work / 'quick_bridge.cpp', work / 'quick_support.py', version_map]}
        if before != after or auxiliary_before != auxiliary_after:
            raise RuntimeError(f'Sources changed during {api} compilation')
        if _tree_hashes(repo / 'src') != original_hashes:
            raise RuntimeError('Original upstream source changed during compilation')
        readelf = subprocess.check_output(['readelf', '--wide', '--dyn-syms',
                                          str(library)], text=True)
        (work / ('exports' + name + '.txt')).write_text(readelf, encoding='utf-8')
        exports = _defined_dynamic_exports(readelf)
        if exports != [api]:
            raise RuntimeError(f'Unexpected defined dynamic exports for {api}: {exports}')
        info['variants'][name] = {
            'api': api, 'library': str(library), 'library_sha256': _sha(library),
            'header_sha256_before': before[HEADER], 'header_sha256_after': after[HEADER],
            'source_sha256_before': before, 'source_sha256_after': after,
            'auxiliary_sha256_before': auxiliary_before,
            'auxiliary_sha256_after': auxiliary_after,
            'flags': command, 'version_map': str(version_map),
            'defined_dynamic_exports': exports, 'readelf': readelf}
    info['libraries'] = {name: variant['library']
                         for name, variant in info['variants'].items()}
    info['link_flags'] = ['-DSUPERSORT_QUICK_THRESHOLD',
                          info['variants']['256']['library'],
                          info['variants']['128']['library'],
                          '-Wl,-rpath,' + str(work)]
    with (work / 'preparation.json').open('x', encoding='utf-8') as f:
        json.dump(info, f, indent=2)
    return info


def archive(info, out):
    """Retain both private source trees, DSOs, scripts, maps, logs and license."""
    work = Path(info['work_dir'])
    for threshold in ('256', '128'):
        variant = info['variants'][threshold]
        if _sha(variant['library']) != variant['library_sha256']:
            raise RuntimeError('DSO changed after preparation')
        if _tree_hashes(work / ('src' + threshold)) != variant['source_sha256_after']:
            raise RuntimeError('Private source changed after preparation')
        current_auxiliary = {name: _sha(work / name)
                             for name in variant['auxiliary_sha256_after']}
        if current_auxiliary != variant['auxiliary_sha256_after']:
            raise RuntimeError('Build wrapper or export map changed after preparation')
    if _tree_hashes(work / 'licenses') != info['license_sha256']:
        raise RuntimeError('Retained upstream licenses changed')
    destination = Path(out) / 'quick'
    # copytree(exist_ok=False) intentionally refuses any existing archive.
    shutil.copytree(work, destination)
    return {'directory': str(destination.resolve()),
            'libraries': {name: str(destination / Path(variant['library']).name)
                          for name, variant in info['variants'].items()}}
