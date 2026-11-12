"""Fixed E036 candidate/control comparisons; no variant selection."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics
import sys

folder=Path(sys.argv[1])
groups=defaultdict(list)
for r in csv.DictReader((folder/'raw.csv').open()):
    groups[int(r['n']),r['distribution'],int(r['seed']),r['algorithm']].append(float(r['ms']))
m={k:statistics.median(v) for k,v in groups.items()}
refs=['std','stdstable','pdq','simd','vq','ips2ra','ips4o']
cases=sorted({k[:3] for k in m})
lines=['# E036 — candidato fijo merge_skip','',
       'Ratios >1 favorecen al candidato. merge_simd es control, excluido del mínimo de referencias. No se selecciona variante por entrada. min/max de muestras conservan la dispersión, sin tratar repeticiones como entradas independientes.','',
       '| n | distribución | semilla | candidato ms | min–max ms | control/candidato | mejor referencia | referencia/candidato |',
       '|---:|---|---:|---:|---|---:|---|---:|']
aggregate=defaultdict(list)
for n,d,s in cases:
    candidate=m[n,d,s,'merge_skip']
    ref=min(refs,key=lambda a:m[n,d,s,a])
    control=m[n,d,s,'merge_simd']/candidate
    ratio=m[n,d,s,ref]/candidate
    v=groups[n,d,s,'merge_skip']
    lines.append(f'| {n} | {d} | {s} | {candidate:.6f} | {min(v):.6f}–{max(v):.6f} | {control:.3f} | {ref} | {ratio:.3f} |')
    aggregate[d].append((control,ratio,n,s))
lines+=['','| distribución | entradas | gana al control | control/candidato mín–máx | gana a referencias | referencia/candidato mín–máx |',
        '|---|---:|---:|---|---:|---|']
for d,v in sorted(aggregate.items()):
    c=[x[0] for x in v];r=[x[1] for x in v]
    lines.append(f'| {d} | {len(v)} | {sum(x>1 for x in c)} | {min(c):.3f}–{max(c):.3f} | {sum(x>1 for x in r)} | {min(r):.3f}–{max(r):.3f} |')
fail=[(d,n,s,c) for d,v in aggregate.items() if d in ['uniform','splitmix'] for c,r,n,s in v if c<1/1.05]
lines+=['','Pérdidas >5% frente al control en uniform/splitmix: '+str(fail),
        '', 'Sin Powersort integrado no se afirma mejorar el estado competitivo de mergesort adaptativo.']
(folder/'analysis-merge.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[-20:]))
