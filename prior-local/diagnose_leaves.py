"""E035: isolated SIMD leaf diagnostic; never a complete-sort ranking."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from datetime import datetime, timezone

p=argparse.ArgumentParser()
p.add_argument('--tag',required=True)
args=p.parse_args()
root=Path(__file__).resolve().parent
out=root/'results'/args.tag
out.mkdir(exist_ok=False)
if platform.system()=='Linux':
    os.sched_setaffinity(0,{2})
else:
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.SetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(),4):raise ctypes.WinError(ctypes.get_last_error())
source=root/'diagnose_leaves.cpp'
before=hashlib.sha256(source.read_bytes()).hexdigest()
exe=out/'diagnose.exe'
simd=root/'vendor'/'x86-simd-sort'
commit=subprocess.check_output(['git','-C',str(simd),'rev-parse','HEAD'],text=True).strip()
assert commit=='6e059b14975df2e3c74260ec905167a1be5a34ca'
flags=['g++','-O3','-march=native','-DNDEBUG','-std=c++17','-I'+str(simd/'src'),str(source),'-o',str(exe)]
subprocess.run(flags,check=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
shutil.copy2(source,out/source.name)
shutil.copy2(Path(__file__),out/'diagnose_leaves.py')
shutil.copy2(root/'notes'/'E035 - Prerregistro diagnóstico.md',out/'preregistration.md')
meta={'utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
      'compiler':subprocess.check_output(['g++','--version'],text=True),'flags':flags,
      'source_sha256':before,'simd_commit':commit,'cpu':2,
      'contract':'isolated leaves; preallocated; copy and exact check excluded; not complete-sort times'}
(out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
for name,extra in [('occupancy.csv',['occupancy']),('leaves.csv',[])]:
    with (out/name).open('w') as f:subprocess.run([str(exe),*extra],stdout=f,check=True)
print('Saved diagnostic to',out)
