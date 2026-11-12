"""Archive the exact current benchmark binary and merge executors, after timing."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
root=Path(__file__).resolve().parent;out=Path(sys.argv[1]).resolve()
meta=json.loads((out/'metadata.json').read_text())
for name,want in meta['source_files_sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==want, name
exe=root/'build/linux/bench.exe';target=out/'bench.bin'
assert not target.exists();shutil.copy2(exe,target)
symbols=subprocess.check_output(['nm','-S','-C','--defined-only',str(exe)],text=True)
selected=[]
for line in symbols.splitlines():
    parts=line.split(maxsplit=3)
    if len(parts)==4 and 'execute_tree_plan<false' in parts[3]:
        address,size=int(parts[0],16),int(parts[1],16)
        asm=subprocess.check_output(['objdump','-d','-C','--no-show-raw-insn',f'--start-address={address}',f'--stop-address={address+size}',str(exe)],text=True)
        selected.append((parts[3],asm))
assert selected
with (out/'merge-assembly.txt').open('x') as f:
    for name,asm in selected:f.write(name+'\n'+asm+'\n')
with (out/'binary.json').open('x') as f:json.dump({'binary_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'executors':[n for n,a in selected],'commands':['nm -S -C --defined-only','objdump -d -C --no-show-raw-insn --start-address --stop-address']},f,indent=2)
shutil.copy2(Path(__file__),out/'inspect_merge.py')
print('Archived',len(selected),'executors and exact binary')
