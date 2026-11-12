"""E037 serial ASan/UBSan verification; distinct from timing runs."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
out=root/'results'/'e037_runs_sanitizers'
out.mkdir(exist_ok=False)
os.sched_setaffinity(0,{2})
files=[root/'verify_runs.cpp',root/'power_bridge.cpp',root/'include/supersort/natural_merge_u32.hpp']
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
exe=out/'verify.exe'
flags=['g++','-O1','-g','-march=native','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer',
       '-I'+str(root/'vendor/x86-simd-sort/src'),str(root/'verify_runs.cpp'),str(root/'power_bridge.cpp'),'-o',str(exe)]
subprocess.run(flags,check=True)
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(root))] for p in files)
for p in files:
    dst=out/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
shutil.copy2(Path(__file__),out/'verify_runs.py')
shutil.copy2(root/'notes/E037 - Prerregistro runs naturales.md',out/'preregistration.md')
meta={'utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'cpu':2,
      'compiler':subprocess.check_output(['g++','--version'],text=True),'flags':flags,'sha256':hashes,
      'power_commit':subprocess.check_output(['git','-C',str(root/'vendor/powersort'),'rev-parse','HEAD'],text=True).strip(),
      'simd_commit':subprocess.check_output(['git','-C',str(root/'vendor/x86-simd-sort'),'rev-parse','HEAD'],text=True).strip(),
      'dependency_sources':'exact Powersort sources retained in sibling e037_runs_verify_linux/vendor/powersort; SIMD fixed commit'}
(out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
with (out/'verification.txt').open('w') as log:
    result=subprocess.run([str(exe)],stdout=log,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit(result.returncode)
print((out/'verification.txt').read_text())
