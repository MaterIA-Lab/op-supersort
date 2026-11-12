"""Serial sanitizer runner for later stages; unique immutable result folders."""
import argparse,hashlib,json,os,platform,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--registration',required=True)
p.add_argument('--defines',nargs='*',default=['SUPERSORT_VERIFY_TREE']);p.add_argument('--quick-threshold',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parent;out=root/'results'/args.tag;out.mkdir(exist_ok=False)
os.sched_setaffinity(0,{2})
files=[root/'verify_runs.cpp',root/'power_bridge.cpp',*list((root/'include').rglob('*.hpp'))]
quick_info=None
if args.quick_threshold:
    import quick_support
    quick_info=quick_support.prepare(root,root/'build/linux',args.tag,sanitize=True)
    args.defines=list(dict.fromkeys([*args.defines,'SUPERSORT_VERIFY_TREE','SUPERSORT_VERIFY_CMOV','SUPERSORT_VERIFY_QUICK']))
    files.extend([root/'quick_bridge.cpp',root/'quick_support.py'])
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
exe=out/'verify.exe'
flags=['g++','-O1','-g','-march=native','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer',
       *['-D'+d for d in args.defines],'-I'+str(root/'vendor/x86-simd-sort/src'),str(root/'verify_runs.cpp'),str(root/'power_bridge.cpp'),'-o',str(exe)]
if quick_info:flags.extend(quick_info['link_flags'])
subprocess.run(flags,check=True)
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(root))] for p in files)
for p in files:
    dst=out/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
shutil.copy2(Path(__file__),out/'verify_stage.py');shutil.copy2(root/args.registration,out/'preregistration.md')
meta={'utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'cpu':2,'compiler':subprocess.check_output(['g++','--version'],text=True),
      'flags':flags,'sha256':hashes,'dependency_sources':'exact Powersort source in corresponding main run; SIMD pinned git commit',
      'vendor':{name:subprocess.check_output(['git','-C',str(root/'vendor'/name),'rev-parse','HEAD'],text=True).strip() for name in ['powersort','x86-simd-sort']}}
if quick_info:
    meta['quick_threshold']=quick_info
    quick_support.archive(quick_info,out)
(out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
with (out/'verification.txt').open('w') as f:result=subprocess.run([str(exe)],stdout=f,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit(result.returncode)
print((out/'verification.txt').read_text())
