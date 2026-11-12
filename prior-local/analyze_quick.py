"""E040 fixed threshold candidate; DSO control and host reference both reported."""
import csv,statistics,sys
from collections import defaultdict
from pathlib import Path
folder=Path(sys.argv[1]);episode=sys.argv[2] if len(sys.argv)>2 else 'E040';g=defaultdict(list)
for r in csv.DictReader((folder/'raw.csv').open()):g[int(r['n']),r['distribution'],int(r['seed']),r['algorithm']].append(float(r['ms']))
m={k:statistics.median(v) for k,v in g.items()};cases=sorted({k[:3] for k in m})
refs=['std','stdstable','pdq','simd','simd256dso','vq','power','ips2ra','ips4o'];agg=defaultdict(list)
lines=[f'# {episode} — principal fijo quick128','',
       'Umbral128 frente a256 con DSOs aislados; referencia host SIMD informada siempre. Ratios>1 favorecen al principal. Casos nominales, no datasets independientes. No elegir ganador por entrada.','',
       '| n | distribución | semilla | principal ms | min–max ms | DSO256/principal | hostSIMD/principal | mejor referencia | referencia/principal |',
       '|---:|---|---:|---:|---|---:|---:|---|---:|']
speed_fail=[];robust_fail=[];host_fail=[]
for n,d,s in cases:
    t=m[n,d,s,'quick128'];v=g[n,d,s,'quick128'];c=m[n,d,s,'simd256dso']/t;h=m[n,d,s,'simd']/t
    ref=min(refs,key=lambda a:m[n,d,s,a]);r=m[n,d,s,ref]/t
    lines.append(f'| {n} | {d} | {s} | {t:.6f} | {min(v):.6f}–{max(v):.6f} | {c:.3f} | {h:.3f} | {ref} | {r:.3f} |')
    agg[d].append((c,h,r))
    if d in ['uniform','splitmix'] and c<=1:speed_fail.append((n,d,s,c))
    if d in ['uniform','splitmix'] and h<=1:host_fail.append((n,d,s,h))
    if d in ['dense16','few','equal','sorted','reverse','skew','alternating','plateaus'] and c<1/1.1:robust_fail.append((n,d,s,c))
lines+=['','| distribución | nominales | gana DSO256 | DSO256/principal | gana hostSIMD | host/principal | gana externas | referencia/principal |',
        '|---|---:|---:|---|---:|---|---:|---|']
for d,rows in sorted(agg.items()):
    chunks=[]
    for i in range(3):
        v=[r[i] for r in rows];chunks.extend([str(sum(x>1 for x in v)),f'{min(v):.3f}–{max(v):.3f}'])
    lines.append('| '+d+' | '+str(len(rows))+' | '+' | '.join(chunks)+' |')
lines+=['','Fallos uniform/SplitMix frente DSO: '+str(speed_fail),'','Pérdidas>10% robustez: '+str(robust_fail),
        '', 'Uniform/SplitMix sin victoria ante hostSIMD: '+str(host_fail),
        '', f'Gana mejor referencia: {sum(r[2]>1 for rows in agg.values() for r in rows)}/{len(cases)} nominales.']
with (folder/'analysis-quick.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
print('\n'.join(lines[-31:]))
