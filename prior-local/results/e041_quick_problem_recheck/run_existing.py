"""Holdout on the exact archived executable/libraries; no compilation or tuning."""
import argparse,csv,hashlib,io,json,os,platform,shutil,statistics,subprocess
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('--from-run',required=True,type=Path);p.add_argument('--tag',required=True)
p.add_argument('--sizes',nargs='+',required=True,type=int);p.add_argument('--seeds',nargs='+',required=True,type=int)
p.add_argument('--distributions',nargs='+',required=True);p.add_argument('--repeats',type=int,default=11);a=p.parse_args()
root=Path(__file__).resolve().parent;origin=(root/a.from_run).resolve();out=root/'results'/a.tag
if out.exists():raise FileExistsError(out)
assert min(a.sizes)>=0 and a.repeats>0
old=json.loads((origin/'metadata.json').read_text());asm=json.loads((origin/'quick-assembly.json').read_text())
assert platform.platform()==old['platform'],'Changed environment'
os.sched_setaffinity(0,{old['logical_cpu']})
exe=origin/'bench.bin';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(exe)==asm['host_binary_sha256']
for name,want in old['source_files_sha256'].items():assert sha(origin/name)==want,name
def verify_libraries():
    for name,path in old['quick_threshold']['libraries'].items():
        assert sha(path)==old['quick_threshold']['variants'][name]['library_sha256'],path
verify_libraries()
out.mkdir()
for name in ['bench.cpp','vq_bridge.cpp','ips_bridge.cpp','power_bridge.cpp','profile_predict.hpp','run.py','quick_bridge.cpp','quick_support.py','bench.bin','quick-assembly.json','quick-assembly.txt']:
    shutil.copy2(origin/name,out/name)
for name in ['include','vendor','quick']:shutil.copytree(origin/name,out/name)
shutil.copy2(Path(__file__),out/'run_existing.py')
algorithms=old['arguments']['algorithms']
meta=dict(old);meta.update({'utc':datetime.now(timezone.utc).isoformat(),
    'arguments':{'sizes':a.sizes,'seeds':a.seeds,'distributions':a.distributions,'repeats':a.repeats,'tag':a.tag,'cpu':old['logical_cpu'],'algorithms':algorithms},
    'reused_executable':str(exe),'reused_from':str(origin),'binary_sha256':sha(exe),
    'orchestrator_sha256':sha(Path(__file__)),'compilation':'NONE; exact archived E040 executable and original linked DSOs, verified before and after run'})
(out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
rows=[]
with (out/'raw.csv').open('x',newline='') as f:
    writer=None
    for n in a.sizes:
        for d in a.distributions:
            for seed in a.seeds:
                print(f'Running exact binary n={n} distribution={d} seed={seed}',flush=True)
                result=subprocess.run([str(exe),str(n),str(a.repeats),d,str(seed),','.join(algorithms)],capture_output=True,text=True,check=True)
                if result.stderr:(out/f'stderr-{n}-{d}-{seed}.txt').write_text(result.stderr)
                batch=list(csv.DictReader(io.StringIO(result.stdout)))
                assert len(batch)==len(algorithms)*a.repeats
                if writer is None:writer=csv.DictWriter(f,fieldnames=batch[0].keys());writer.writeheader()
                writer.writerows(batch);f.flush();rows.extend(batch)
verify_libraries();assert sha(exe)==asm['host_binary_sha256']
groups={}
for r in rows:groups.setdefault((int(r['n']),r['distribution'],r['algorithm']),[]).append(float(r['ms']))
lines=['# Resultados','','Mismo ejecutable y DSOs de E040, sin compilación. Repeticiones no son datasets independientes.','',
       '| n | distribución | algoritmo | mediana ms |','|---:|---|---|---:|']
for (n,d,alg),v in sorted(groups.items()):lines.append(f'| {n} | {d} | {alg} | {statistics.median(v):.6f} |')
with (out/'summary.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
print('Saved',len(rows),'samples to',out)
