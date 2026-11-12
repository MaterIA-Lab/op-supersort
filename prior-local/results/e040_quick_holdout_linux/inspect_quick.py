"""Archive exact E040 host and DSO disassembly after all timing is complete."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
root=Path(__file__).resolve().parent;out=Path(sys.argv[1]).resolve()
meta=json.loads((out/'metadata.json').read_text());info=meta['quick_threshold']
for name,want in meta['source_files_sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==want,name
binary=root/'build/linux/bench.exe';target=out/'bench.bin';assert not target.exists();shutil.copy2(binary,target)
observed={};full=[]
for threshold,lib in info['libraries'].items():
    path=Path(lib);assert hashlib.sha256(path.read_bytes()).hexdigest()==info['variants'][threshold]['library_sha256']
    symbols=subprocess.check_output(['nm','-S','-C','--defined-only',str(path)],text=True)
    selected=[]
    for line in symbols.splitlines():
        parts=line.split(maxsplit=3)
        if len(parts)!=4:continue
        name=parts[3]
        if ('sort_n_vec<' not in name or 'unsigned int' not in name) and name!='ss_xss'+threshold:continue
        address,size=int(parts[0],16),int(parts[1],16)
        asm=subprocess.check_output(['objdump','-d','-C','--no-show-raw-insn',f'--start-address={address}',f'--stop-address={address+size}',str(path)],text=True)
        # rbp may be a general data pointer under frame-pointer omission.
        # Count only explicit rsp references; do not label arbitrary rbp data as stack.
        stack_lines=[l.strip() for l in asm.splitlines() if '%rsp' in l and ('%ymm' in l or '%xmm' in l)]
        selected.append({'symbol':name,'bytes':size,'vector_stack_instruction_lines':stack_lines})
        full.append('DSO '+threshold+' '+name+'\n'+asm+'\n')
    observed[threshold]=selected
with (out/'quick-assembly.txt').open('x') as f:f.write('\n'.join(full))
with (out/'quick-assembly.json').open('x') as f:json.dump({'host_binary_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'symbols':observed,
    'interpretation':'stack operand references are static evidence, not measured spills, DRAM traffic or cycle attribution'},f,indent=2)
shutil.copy2(Path(__file__),out/'inspect_quick.py')
print({t:[(x['symbol'],x['bytes'],len(x['vector_stack_instruction_lines'])) for x in v] for t,v in observed.items()})
