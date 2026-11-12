"""E039 fixed scalar selection-kernel contrast; immutable outputs."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics,sys
folder=Path(sys.argv[1]);g=defaultdict(list)
for r in csv.DictReader((folder/'raw.csv').open()):g[int(r['n']),r['distribution'],int(r['seed']),r['algorithm']].append(float(r['ms']))
m={k:statistics.median(v) for k,v in g.items()};cases=sorted({k[:3] for k in m})
refs=['std','stdstable','pdq','simd','vq','power','ips2ra','ips4o']
lines=['# E039 — principal fijo merge_tree_cmov','',
       'Ratios>1 favorecen al principal. Control kernel std::merge, mismo árbol y memoria; E037 como control práctico. No elegir variantes por entrada. Casos nominales no son datasets independientes. La interpretación de ramas requiere merge-assembly.txt del binario exacto.','',
       '| n | distribución | semilla | principal ms | min–max ms | stdmerge/principal | E037/principal | Power/principal | mejor referencia | referencia/principal |',
       '|---:|---|---:|---:|---|---:|---:|---:|---|---:|']
agg=defaultdict(list);speed_fail=[];robust_fail=[];same=0
for n,d,s in cases:
    t=m[n,d,s,'merge_tree_cmov'];v=g[n,d,s,'merge_tree_cmov'];c=m[n,d,s,'merge_tree_power']/t
    old=m[n,d,s,'merge_natural']/t;p=m[n,d,s,'power']/t;ref=min(refs,key=lambda a:m[n,d,s,a]);r=m[n,d,s,ref]/t
    lines.append(f'| {n} | {d} | {s} | {t:.6f} | {min(v):.6f}–{max(v):.6f} | {c:.3f} | {old:.3f} | {p:.3f} | {ref} | {r:.3f} |')
    agg[d].append((c,old,p,r))
    rows=list(csv.DictReader((folder/f'diagnostic-{n}-{d}-{s}.csv').open()))
    assert len(rows)==2 and rows[0]['mode']=='weighted' and rows[1]['mode']=='cmov'
    assert all(rows[0][k]==rows[1][k] for k in rows[0] if k!='mode'),(n,d,s)
    same+=1
    if d in ['uniform','splitmix'] and c<=1:speed_fail.append((n,d,s,c))
    if d in ['dense16','few','equal','skew','forced_front','forced_middle','forced_tail'] and c<1/1.1:robust_fail.append((n,d,s,c))
lines+=['','| distribución | nominales | gana control | control/principal | gana E037 | E037/principal | gana Power | Power/principal | gana externas | referencia/principal |',
        '|---|---:|---:|---|---:|---|---:|---|---:|---|']
for d,rows in sorted(agg.items()):
    chunks=[]
    for i in range(4):
        v=[r[i] for r in rows];chunks.extend([str(sum(x>1 for x in v)),f'{min(v):.3f}–{max(v):.3f}'])
    lines.append('| '+d+' | '+str(len(rows))+' | '+' | '.join(chunks)+' |')
lines+=['',f'Contadores y hashes idénticos: {same}/{len(cases)}.', '', 'Fallos de velocidad uniform/SplitMix: '+str(speed_fail),'','Pérdidas>10% en familias de robustez: '+str(robust_fail),
        '',f'Gana mejor referencia: {sum(r[3]>1 for rows in agg.values() for r in rows)}/{len(cases)} nominales.']
with (folder/'analysis-kernel.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
print('\n'.join(lines[-30:]))
