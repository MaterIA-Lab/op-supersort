"""Summarize completed runs without treating repeated timings as new datasets."""
import csv
import argparse
from pathlib import Path
import statistics
p = argparse.ArgumentParser()
p.add_argument('folder', type=Path)
p.add_argument('--candidate', help='Fixed candidate; avoids retrospective variant selection')
args = p.parse_args()
folder = args.folder
groups = {}
for row in csv.DictReader((folder / 'raw.csv').open()):
    key = (int(row['n']), row['distribution'], int(row['seed']), row['algorithm'])
    groups.setdefault(key, []).append(float(row['ms']))
medians = {key: statistics.median(values) for key, values in groups.items()}
cases = sorted({key[:3] for key in medians})
description = ('Candidato fijo: '+args.candidate if args.candidate else 'Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.')
lines = ['# Comparación por entrada', '',
         'Cada fila resume las medianas de las repeticiones de una entrada. '+description, '',
         '| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |',
         '|---:|---|---:|---|---:|---|---:|---:|']
for n, dist, seed in cases:
    candidates = {key[3]: value for key, value in medians.items() if key[:3] == (n, dist, seed)}
    local = args.candidate or min((x for x in candidates if x.startswith(('local', 'predict', 'two', 'adaptive', 'merge', 'quick'))), key=candidates.get)
    ref = min((x for x in candidates if not x.startswith(('local', 'predict', 'two', 'adaptive', 'merge', 'quick'))), key=candidates.get)
    lines.append(f'| {n} | {dist} | {seed} | {local} | {candidates[local]:.3f} | {ref} | {candidates[ref]:.3f} | {candidates[ref]/candidates[local]:.3f} |')
name = 'comparison-'+args.candidate+'.md' if args.candidate else 'comparison.md'
(folder / name).write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('\n'.join(lines))
