"""Preregistered E042: separate instrumented source copies, never rank their time."""
import argparse,csv,difflib,hashlib,io,json,os,platform,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
import quick_support

ROOT=Path(__file__).resolve().parent
ORIGIN=ROOT/'results/e040_quick_holdout_linux'
OUT=ROOT/'results/e042_work_diagnostic'
CASES=[(8193,'skew',33013),(8193,'uniform',33013),
       (180013,'splitmix',14009),(180013,'few',58013),
       (8209,'forced_middle',58013),(8209,'forced_tail',41011),
       (8209,'forced_front',58013),(180013,'uniform',41011),
       (1500007,'splitmix',58013),(180013,'equal',14009),
       (180013,'sorted',14009),(180013,'alternating',14009)]
SIZES=[0,1,2,7,8,9,15,16,17,31,32,33,63,64,65,127,128,129,255,256,257,
       511,512,513,8193,8209,65539,180013]
PREREG=ROOT/'notes/E042 - Prerregistro trabajo y procesos.md'
sha=quick_support._sha
tree=quick_support._tree_hashes

def instrument(raw):
    text=raw.decode('utf-8')
    start=text.index('static void qsort_(')
    end=text.index('template <typename vtype, typename comparator, typename type_t>\nX86_SIMD_SORT_INLINE void qselect_',start)
    before,body,after=text[:start],text[start:end],text[end:]
    def replace(old,new):
        nonlocal body
        if body.count(old)!=1:raise RuntimeError('Ambiguous diagnostic insertion: '+old)
        body=body.replace(old,new)
    replace('                   arrsize_t task_threshold)\n{',
            '                   arrsize_t task_threshold)\n{\n    E042Node e042_node(right + 1 - left, max_iters);')
    replace('    if (max_iters <= 0) {',
            '    if (max_iters <= 0) {\n        ++e042_stats.fallback; e042_stats.fallback_elements += right + 1 - left;\n        e042_mix(2);')
    replace('    if (right + 1 - left <= vtype::network_sort_threshold) {',
            '    if (right + 1 - left <= vtype::network_sort_threshold) {\n        e042_leaf(right + 1 - left);')
    replace('    if (pivot_result.result == pivot_result_t::Sorted) { return; }',
            '    if (pivot_result.result == pivot_result_t::Sorted) {\n        ++e042_stats.sorted; e042_stats.sorted_elements += right + 1 - left;\n        e042_mix(3); return;\n    }')
    replace('    if (pivot_result.result == pivot_result_t::Only2Values) { return; }',
            '    ++e042_stats.partitions; e042_stats.partition_elements += right + 1 - left;\n'
            '    e042_mix(4); e042_mix(pivot_index-left); e042_mix(uint64_t(pivot));\n'
            '    if (pivot_result.result == pivot_result_t::Only2Values) {\n'
            '        ++e042_stats.only2; e042_stats.only2_elements += right + 1 - left; return;\n    }')
    replace('#ifdef XSS_COMPILE_OPENMP',
            '    if (pivot == leftmostValue) e042_stats.skipped_equal_elements += pivot_index-left;\n'
            '    if (pivot == rightmostValue) e042_stats.skipped_equal_elements += right+1-pivot_index;\n'
            '#ifdef XSS_COMPILE_OPENMP')
    return (before+body+after).encode('utf-8')

def build():
    if platform.system()!='Linux':raise RuntimeError('Use original Linux environment')
    OUT.mkdir(exist_ok=False)
    old=json.loads((ORIGIN/'metadata.json').read_text())
    if platform.platform()!=old['platform']:raise RuntimeError('Environment changed')
    os.sched_setaffinity(0,{2})
    for name in ['e042_work.py','e042_work.cpp','e042_bridge.cpp','e042_stats.hpp']:
        shutil.copy2(ROOT/name,OUT/name)
    shutil.copy2(PREREG,OUT/PREREG.name)
    bench=(ORIGIN/'bench.cpp').read_bytes()
    if sha(ORIGIN/'bench.cpp')!=old['source_files_sha256']['bench.cpp']:raise RuntimeError('Generator source mismatch')
    generator=bench[bench.index(b'V generate('):bench.index(b'int main(')]
    (OUT/'e042_generator.inc').write_bytes(generator)
    shutil.copytree(ORIGIN/'quick/licenses',OUT/'licenses')
    meta={'utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
          'logical_cpu':2,'compiler':subprocess.check_output(['g++','--version'],text=True),
          'origin':str(ORIGIN),'cases':CASES,'sizes':SIZES,
          'distributions':old['arguments']['distributions'],
          'generator_sha256':hashlib.sha256(generator).hexdigest(),'variants':{},
          'contract':'UNTIMED instrumentation; exact output/std::sort and guards, no performance ranking'}
    for threshold in (256,128):
        name=str(threshold);source=OUT/('src'+name)
        shutil.copytree(ORIGIN/'quick'/('src'+name),source)
        if tree(source)!=old['quick_threshold']['variants'][name]['source_sha256_after']:
            raise RuntimeError('Source differs from E040')
        target=source/'xss-common-qsort.h';original=target.read_bytes()
        modified=instrument(original);target.write_bytes(modified)
        patch=''.join(difflib.unified_diff(original.decode().splitlines(True),modified.decode().splitlines(True),
                     fromfile='E040/xss-common-qsort.h',tofile='E042/xss-common-qsort.h'))
        (OUT/('instrument'+name+'.patch')).write_text(patch)
        exports=OUT/('exports'+name+'.map');api='e042_xss'+name
        exports.write_text('{\n global: '+api+';\n local: *;\n};\n')
        meta['variants'][name]={'source_sha256':tree(source),'api':api,'builds':{}}
    frozen=tree(OUT)
    # Sequential compilation, all input files already snapshotted and frozen.
    for mode in ('o3','san'):
        folder=OUT/mode;folder.mkdir()
        opt=['-O3','-DNDEBUG'] if mode=='o3' else ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
        libraries=[]
        for threshold in (256,128):
            name=str(threshold);library=folder/('libe042_xss'+name+'.so');api='e042_xss'+name
            command=['g++',*opt,'-march=native','-std=c++17','-shared','-fPIC','-fvisibility=hidden','-Wl,-Bsymbolic',
                     '-DE042_INSTRUMENT','-DSORT_API='+api,'-DEXPECTED_THRESHOLD='+name,
                     '-I'+str(OUT/('src'+name)),str(OUT/'e042_bridge.cpp'),
                     '-Wl,--version-script='+str(OUT/('exports'+name+'.map')),'-o',str(library)]
            print('Compiling',mode,name,flush=True)
            result=subprocess.run(command,capture_output=True,text=True)
            (folder/('compile'+name+'.log')).write_text(result.stdout+result.stderr)
            if result.returncode:raise RuntimeError('Compilation failed: '+str(library))
            exports=subprocess.check_output(['readelf','--wide','--dyn-syms',str(library)],text=True)
            (folder/('exports'+name+'.txt')).write_text(exports)
            if quick_support._defined_dynamic_exports(exports)!=[api]:raise RuntimeError('Symbol leakage')
            meta['variants'][name]['builds'][mode]={'flags':command,'sha256':sha(library)}
            libraries.append(str(library))
        command=['g++',*opt,'-march=native','-std=c++17',str(OUT/'e042_work.cpp'),*libraries,
                 '-Wl,-rpath,'+str(folder),'-o',str(folder/'work.bin')]
        result=subprocess.run(command,capture_output=True,text=True)
        (folder/'compile-host.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Diagnostic host compilation failed')
        meta[mode]={'flags':command,'sha256':sha(folder/'work.bin')}
        for name,want in frozen.items():
            if sha(OUT/name)!=want:raise RuntimeError('Frozen input changed: '+name)
    meta['frozen_inputs']=frozen
    with (OUT/'metadata.json').open('x') as f:json.dump(meta,f,indent=2)
    print('Build complete; performance E040 binaries unchanged',flush=True)

def verify():
    meta=json.loads((OUT/'metadata.json').read_text())
    for name,want in meta['frozen_inputs'].items():
        if sha(OUT/name)!=want:raise RuntimeError('Frozen source changed '+name)
    for mode in ('o3','san'):
        if sha(OUT/mode/'work.bin')!=meta[mode]['sha256']:raise RuntimeError('Host changed')
        for name in ('256','128'):
            if sha(OUT/mode/('libe042_xss'+name+'.so'))!=meta['variants'][name]['builds'][mode]['sha256']:
                raise RuntimeError('DSO changed')
    return meta

def run(mode):
    meta=verify();os.sched_setaffinity(0,{2})
    destination=OUT/('work.csv' if mode=='o3' else 'sanitizers.csv')
    cases=[(p,*c) for p in range(3) for c in CASES] if mode=='o3' else (
          [(0,n,d,s) for n in SIZES for d in meta['distributions'] for s in (12007,33013)]
          +[(1,*c) for c in CASES])
    env=dict(os.environ)
    if mode=='san':
        env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
    count=0
    with destination.open('x',newline='') as f:
        writer=None
        for i,(p,n,d,s) in enumerate(cases):
            result=subprocess.run([str(OUT/mode/'work.bin'),str(n),d,str(s)],capture_output=True,text=True,env=env)
            if result.stderr:
                (OUT/f'{mode}-stderr-{i}.txt').write_text(result.stderr)
            if result.returncode:raise RuntimeError(f'{mode} failed at {n}/{d}/{s}; no retries')
            rows=list(csv.DictReader(io.StringIO(result.stdout)))
            if len(rows)!=6:raise RuntimeError('Wrong diagnostic row count')
            rows=[{'process_round':p,**r} for r in rows]
            if writer is None:writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader()
            writer.writerows(rows);f.flush();count+=len(rows)
            if i%50==0 or i+1==len(cases):print(mode,i+1,'/',len(cases),'checked',count,flush=True)
    verify()
    with (OUT/(mode+'-complete.json')).open('x') as f:json.dump({'checked_outputs':count,'subprocesses':len(cases)},f)

def analyze():
    from collections import defaultdict
    rows=list(csv.DictReader((OUT/'work.csv').open()));groups=defaultdict(list)
    ignored={'process_round','offset','data_address'}
    for r in rows:groups[r['n'],r['distribution'],r['seed'],r['threshold']].append(r)
    for k,rs in groups.items():
        values={tuple((a,b) for a,b in r.items() if a not in ignored) for r in rs}
        if len(values)!=1:raise RuntimeError('Non-deterministic work counts: '+str(k))
    lines=['# E042 — trabajo instrumentado','','Sin tiempos instrumentados en ranking. Mismas cuentas en tres procesos y offsets0/1/7 para cada entrada/umbral. No prueba de causalidad de tiempos.','',
           '| n | distribución | semilla | umbral | particiones | elementos partición | hojas | elementos hojas | profundidad máxima | Sorted | Only2 | fallback/elementos |',
           '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for n,d,s in CASES:
        for t in (256,128):
            r=groups[str(n),d,str(s),str(t)][0]
            lines.append(f'| {n} | {d} | {s} | {t} | '+ ' | '.join(r[k] for k in ['partitions','partition_elements','leaves','leaf_elements','max_depth','sorted','only2'])+f" | {r['fallback']}/{r['fallback_elements']} |")
    lines+=['','Las bandas de hojas completas, hashes de trayectoria y direcciones están en work.csv. Un elemento puede contarse en varias particiones; no son bytes DRAM. Sorted/Only2Values describen salidas del pivote upstream. No medir instrucciones de std::sort ni comparar tiempos O3/O1.','',
            'Validación: '+(OUT/'o3-complete.json').read_text()+', sanitizadores: '+(OUT/'san-complete.json').read_text()+'. Todos con igualdad exacta/std::sort y guardas. No prueba formal.']
    with (OUT/'analysis.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['build','work','sanitize','analyze']);a=p.parse_args()
    {'build':build,'work':lambda:run('o3'),'sanitize':lambda:run('san'),'analyze':analyze}[a.phase]()
