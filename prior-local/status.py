"""Index completed experiments, preserving each experiment's own protocol."""
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parent
lines = ['# Índice de experimentos', '',
         'Tiempos de protocolos distintos no se deben comparar como una única serie. Cada carpeta conserva metadatos, muestras y fuentes. Solo se incluyen ejecuciones completas.', '',
         '| experimento | entradas | algoritmos | muestras medidas | salidas verificadas incl. calentamiento | CPU lógica |',
         '|---|---:|---:|---:|---:|---|']
total = checked_total = 0
for folder in sorted((root / 'results').iterdir()):
    if not folder.is_dir() or not (folder / 'summary.md').exists():
        continue
    meta = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    with (folder / 'raw.csv').open() as f:
        rows = list(csv.DictReader(f))
    cases = {(r['n'], r['distribution'], r['seed']) for r in rows}
    algorithms = {r['algorithm'] for r in rows}
    # E042 reused each array in distinct processes, with a warmup in each.
    warmups = len({(r.get('process_batch'), r.get('process_order'), r['n'],
                    r['distribution'], r['seed'], r['algorithm']) for r in rows})
    checked = len(rows) + warmups
    total += len(rows)
    checked_total += checked
    cpu = meta.get('logical_cpu', 'sin fijar')
    lines.append(f'| [{folder.name}]({folder.name}/summary.md) | {len(cases)} | {len(algorithms)} | {len(rows)} | {checked} | {cpu} |')
lines += ['', f'Total: {total:,} muestras medidas y {checked_total:,} salidas comprobadas exactamente con std::sort, contando calentamientos.',
          '', 'Las salidas verificadas no equivalen a datasets independientes; una misma entrada se reutiliza en muchas repeticiones.']
(root / 'results' / 'index.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(lines[-3])
