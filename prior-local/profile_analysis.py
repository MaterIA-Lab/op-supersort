import csv
from pathlib import Path
import statistics
import sys

folder = Path(sys.argv[1])
lines = ['# Diagnóstico por fases', '', 'Microsegundos; medianas tras excluir el primer calentamiento. profile es una copia instrumentada: no asumir idéntico comportamiento que el kernel sin instrumentar.', '',
         '| caso | alloc | scatter | sort+copy | free | scratch mod4096 |', '|---|---:|---:|---:|---:|---|']
for file in sorted(folder.glob('diagnostic-*.csv')):
    rows = list(csv.DictReader(file.open()))[1:]
    values = [statistics.median(float(r[k]) for r in rows) for k in ['allocate_us','scatter_us','sortcopy_us','free_us']]
    addresses = sorted({int(r['scratch_mod4096']) for r in rows})
    lines.append('| '+file.stem.removeprefix('diagnostic-')+' | '+' | '.join(f'{v:.2f}' for v in values)+' | '+str(addresses)+' |')
(folder / 'phases.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))
