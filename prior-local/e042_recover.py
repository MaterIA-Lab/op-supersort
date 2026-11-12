"""One preregistered sanitizer recovery: non-PIE persistent host, same DSOs."""
import csv,hashlib,io,json,os,platform,resource,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
import e042_work as work

def main():
    meta=work.verify();os.sched_setaffinity(0,{2})
    root=work.ROOT;origin=work.OUT;out=root/'results/e042_sanitizer_recovery'
    out.mkdir(exist_ok=False)
    shutil.copy2(__file__,out/'e042_recover.py')
    shutil.copy2(root/'e042_work.py',out/'e042_work.py')
    shutil.copy2(root/'quick_support.py',out/'quick_support.py')
    shutil.copy2(root/'notes/E042 - Adenda sanitizadores.md',out/'preregistration.md')
    for name in ['e042_work.cpp','e042_stats.hpp','e042_generator.inc']:
        shutil.copy2(origin/name,out/name)
    raw=(origin/'e042_work.cpp').read_text()
    raw=raw.replace('int main(int argc,char** argv)', 'int e042_case(int argc,char** argv)',1)
    pos=raw.rfind('\n}')
    if pos<0 or raw[pos:].strip()!='}':raise RuntimeError('Unexpected host structure')
    raw=raw[:pos]+'\n    return 0;'+raw[pos:]
    raw+='''
int main() {
    std::string n,d,seed;
    while(std::cin>>n>>d>>seed) {
        char program[]="e042";
        char* args[]={program,n.data(),d.data(),seed.data()};
        int result=e042_case(4,args);
        std::cout.flush();
        if(result)return result;
    }
    return std::cin.eof()?0:3;
}
'''
    (out/'persistent.cpp').write_text(raw)
    cases=[(n,d,s) for n in work.SIZES for d in meta['distributions'] for s in (12007,33013)]+work.CASES
    (out/'cases.txt').write_text(''.join(f'{n} {d} {s}\n' for n,d,s in cases))
    libs=[origin/'san'/('libe042_xss'+t+'.so') for t in ('256','128')]
    flags=['g++','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',
           '-fno-pie','-no-pie','-march=native','-std=c++17',str(out/'persistent.cpp'),
           *map(str,libs),'-Wl,-rpath,'+str(origin/'san'),'-o',str(out/'persistent.bin')]
    frozen={p.name:work.sha(p) for p in out.iterdir() if p.is_file()}
    print('Compiling persistent non-PIE sanitizer host',flush=True)
    result=subprocess.run(flags,capture_output=True,text=True)
    (out/'compile.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Recovery compilation failed')
    work.verify()
    if any(work.sha(out/n)!=h for n,h in frozen.items()):raise RuntimeError('Input changed')
    info={'utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
          'flags':flags,'frozen_inputs':frozen,'binary_sha256':work.sha(out/'persistent.bin'),
          'linked_original_sanitizer_libraries':{str(p):work.sha(p) for p in libs},
          'cases':len(cases),'expected_checks':len(cases)*6,'timeout_seconds':120,
          'stderr_stdout_limit_bytes':16*1024*1024,'original_failure_preserved':str(origin/'san-stderr-1.txt')}
    with (out/'metadata.json').open('x') as f:json.dump(info,f,indent=2)
    def bounded():resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
             UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    with (out/'cases.txt').open() as inp,(out/'stdout.csv').open('x') as stdout,(out/'stderr.txt').open('x') as stderr:
        try:
            result=subprocess.run([str(out/'persistent.bin')],stdin=inp,stdout=stdout,stderr=stderr,
                                  env=env,preexec_fn=bounded,timeout=120)
            returncode=result.returncode
        except subprocess.TimeoutExpired:returncode='timeout'
    work.verify()
    lines=(out/'stdout.csv').read_text().splitlines()
    filtered=[s for i,s in enumerate(lines) if i==0 or not s.startswith('n,distribution,seed,threshold,')]
    rows=list(csv.DictReader(filtered))
    complete=returncode==0 and len(rows)==info['expected_checks'] and (out/'stderr.txt').stat().st_size==0
    completion={'returncode':returncode,'checked_outputs':len(rows),'complete':complete,
                'stderr_bytes':(out/'stderr.txt').stat().st_size}
    with (out/'completion.json').open('x') as f:json.dump(completion,f,indent=2)
    with (out/'verification.md').open('x',encoding='utf-8') as f:
        f.write('# E042 — recuperación de sanitizadores\n\n'+json.dumps(completion)+'\n\n'
                'Mismas bibliotecas instrumentadas; nuevo host noPIE y un proceso persistente. '
                'No establece la causa del fallo inicial, que permanece archivado. '
                'Comprobación exacta/std::sort, guardas y límites/cuentas por cada salida.\n')
    print(completion,flush=True)
    if not complete:raise RuntimeError('Recovery incomplete; no retries')

if __name__=='__main__':main()
