"""E037: fixed candidate, controls and diagnostics; never choose variants."""
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
refs=['std','stdstable','pdq','simd','vq','power','ips2ra','ips4o']
cases=sorted({k[:3] for k in m})
lines=['# E037 — candidato fijo merge_natural','',
       'Ratios >1 favorecen al principal. Controles merge_fixedruns/merge_skip excluidos del mínimo de referencias externas. Semillas repetidas de equal/alternating/plateaus no son datasets independientes. Todas las medianas y rangos de muestras se conservan, sin seleccionar ganadores.','',
       '| n | distribución | semilla | principal ms | min–max ms | fixed/principal | anterior/principal | Power/principal | mejor referencia | referencia/principal |',
       '|---:|---|---:|---:|---|---:|---:|---:|---|---:|']
aggregate=defaultdict(list)
diagnostic=['# E037 — contadores fuera de tiempo','',
            'Misma implementación con contadores activados; salidas verificadas. Escrituras lógicas = mezcladas + copiadas por nivel + copia final; no incluyen hojas/inversión/descriptores y NO son bytes DRAM. No se compara su tiempo.','',
            '| n | distribución | semilla | runs fixed/natural | niveles fixed/natural | elementos SIMD natural | invertidos natural | escrituras fixed/natural |',
            '|---:|---|---:|---|---|---:|---:|---|']
for n,d,s in cases:
    t=m[n,d,s,'merge_natural'];v=groups[n,d,s,'merge_natural']
    ref=min(refs,key=lambda a:m[n,d,s,a])
    c=m[n,d,s,'merge_fixedruns']/t
    ratio=m[n,d,s,ref]/t
    power=m[n,d,s,'power']/t
    lines.append(f'| {n} | {d} | {s} | {t:.6f} | {min(v):.6f}–{max(v):.6f} | {c:.3f} | {m[n,d,s,"merge_skip"]/t:.3f} | {power:.3f} | {ref} | {ratio:.3f} |')
    aggregate[d].append((c,ratio,power,n,s))
    rows={r['mode']:r for r in csv.DictReader((folder/f'diagnostic-{n}-{d}-{s}.csv').open())}
    writes={}
    for mode,r in rows.items():
        body=int(r['merged_elements'])+int(r['copied_elements'])
        assert body==n*int(r['levels']), (n,d,s,mode)
        writes[mode]=body+int(r['final_elements'])
    a,b=rows['fixed'],rows['natural']
    diagnostic.append(f'| {n} | {d} | {s} | {a["runs"]}/{b["runs"]} | {a["levels"]}/{b["levels"]} | {b["simd_elements"]} | {b["reversed_elements"]} | {writes["fixed"]}/{writes["natural"]} |')
lines+=['','| distribución | casos nominales | gana control | fixed/principal mín–máx | gana externas | referencia/principal mín–máx | gana Power | Power/principal mín–máx |',
        '|---|---:|---:|---|---:|---|---:|---|']
for d,v in sorted(aggregate.items()):
    c=[x[0] for x in v];r=[x[1] for x in v];p=[x[2] for x in v]
    lines.append(f'| {d} | {len(v)} | {sum(x>1 for x in c)} | {min(c):.3f}–{max(c):.3f} | {sum(x>1 for x in r)} | {min(r):.3f}–{max(r):.3f} | {sum(x>1 for x in p)} | {min(p):.3f}–{max(p):.3f} |')
mechanism_fail=[(d,n,s,c) for d,v in aggregate.items() if d in ['sorted','reverse','equal','runs4096'] for c,r,p,n,s in v if c<=1]
overhead_fail=[(d,n,s,c) for d,v in aggregate.items() if d in ['uniform','splitmix'] for c,r,p,n,s in v if c<1/1.10]
lines+=['','Fallas del criterio de mecanismo: '+str(mechanism_fail),
        '', 'Pérdidas >10% frente al control en uniform/splitmix: '+str(overhead_fail),
        '', f'Principal gana frente a mejor referencia: {sum(r>1 for v in aggregate.values() for c,r,p,n,s in v)}/{len(cases)} casos nominales.',
        '', 'Dos comprobaciones extra por entrada corresponden al diagnóstico y se contabilizan aparte del índice normal.']
for name,content in [('analysis-runs.md',lines),('movement-summary.md',diagnostic)]:
    path=folder/name
    with path.open('x',encoding='utf-8') as f:f.write('\n'.join(content)+'\n')
print('\n'.join(lines[-26:]))
