"""E038 fixed tree policy contrast, preregistered structural checks."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics
import sys
folder=Path(sys.argv[1]);g=defaultdict(list)
for r in csv.DictReader((folder/'raw.csv').open()):
    g[int(r['n']),r['distribution'],int(r['seed']),r['algorithm']].append(float(r['ms']))
m={k:statistics.median(v) for k,v in g.items()}
cases=sorted({k[:3] for k in m});refs=['std','stdstable','pdq','simd','vq','power','ips2ra','ips4o']
expected={140009:(1258993,420033,507503),270011:(2427995,810035,978751),530017:(4766017,1590057,1921265),1200011:(10790731,3600035,4350027)}
lines=['# E038 — principal fijo merge_tree_power','',
       'Ratios>1 favorecen al principal. No elegir variantes por entrada. Semillas de equal/alternating/plateaus repiten datos. Controles excluidos del mínimo externo.','',
       '| n | distribución | semilla | principal ms | min–max ms | pair/principal | E037/principal | Power/principal | mejor referencia | referencia/principal |',
       '|---:|---|---:|---:|---|---:|---:|---:|---|---:|']
diag=['# E038 — planes y movimientos fuera de tiempo','',
      'r-1 operaciones, hash de runs idéntico y copyback=C_exec comprobados. Tráfico lógico aproximado de fusiones16*C_exec bytes; no DRAM.','',
      '| n | distribución | semilla | runs | C_tree pair/power | C_exec pair/power | omitidas pair/power |',
      '|---:|---|---:|---:|---|---|---|']
agg=defaultdict(list);bad_model=[];bad_speed=[];bad_overhead=[]
for n,d,s in cases:
    t=m[n,d,s,'merge_tree_power'];v=g[n,d,s,'merge_tree_power']
    c=m[n,d,s,'merge_tree_pair']/t;old=m[n,d,s,'merge_natural']/t;p=m[n,d,s,'power']/t
    ref=min(refs,key=lambda a:m[n,d,s,a]);ratio=m[n,d,s,ref]/t
    lines.append(f'| {n} | {d} | {s} | {t:.6f} | {min(v):.6f}–{max(v):.6f} | {c:.3f} | {old:.3f} | {p:.3f} | {ref} | {ratio:.3f} |')
    agg[d].append((c,old,p,ratio))
    a={r['mode']:{k:(v if k=='mode' else int(v)) for k,v in r.items()} for r in csv.DictReader((folder/f'diagnostic-{n}-{d}-{s}.csv').open())}
    pair,power=a['pair'],a['weighted']
    assert all(pair[k]==power[k] for k in ['runs','run_hash','simd_elements','reversed_elements'])
    for r in [pair,power]:
        assert r['operations']==r['runs']-1
        assert r['copied_elements']==r['executed_elements']<=r['tree_elements']
    if d.startswith('forced_'):
        u,f,mid=expected[n];want={'forced_front':(u,f),'forced_middle':(u,mid),'forced_tail':(f,f)}[d]
        got=(pair['tree_elements'],power['tree_elements'])
        if got!=want or pair['runs']!=257 or any(r['executed_elements']!=r['tree_elements'] for r in [pair,power]):bad_model.append((n,d,s,got,want))
    if d in ['forced_front','forced_middle'] and c<=1:bad_speed.append((n,d,s,c))
    if d in ['uniform','splitmix'] and c<1/1.1:bad_overhead.append((n,d,s,c))
    diag.append(f'| {n} | {d} | {s} | {pair["runs"]} | {pair["tree_elements"]}/{power["tree_elements"]} | {pair["executed_elements"]}/{power["executed_elements"]} | {pair["skipped"]}/{power["skipped"]} |')
lines+=['','| distribución | nominales | gana pair | pair/principal | gana E037 | E037/principal | gana Power | Power/principal | gana externas | referencia/principal |',
        '|---|---:|---:|---|---:|---|---:|---|---:|---|']
for d,rows in sorted(agg.items()):
    chunks=[]
    for i in range(4):
        v=[r[i] for r in rows];chunks.extend([str(sum(x>1 for x in v)),f'{min(v):.3f}–{max(v):.3f}'])
    lines.append('| '+d+' | '+str(len(rows))+' | '+' | '.join(chunks)+' |')
lines+=['','Fallos estructurales: '+str(bad_model),'','Fallos de velocidad front/middle: '+str(bad_speed),'','Pérdidas>10% uniform/splitmix: '+str(bad_overhead),
        '',f'Gana mejor referencia: {sum(r[3]>1 for rows in agg.values() for r in rows)}/{len(cases)} casos nominales.']
for name,data in [('analysis-tree.md',lines),('tree-movement.md',diag)]:
    with (folder/name).open('x',encoding='utf-8') as f:f.write('\n'.join(data)+'\n')
print('\n'.join(lines[-32:]))
