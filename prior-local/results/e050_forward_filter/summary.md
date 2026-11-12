# E050 — Separación in situ con ventana preparada

Cada cociente divide la mediana de la referencia por la de forward. La puerta usa vq para el 50/50 y scalar_scratch para el 95/5.

| Familia | Semilla | Inferiores | Internos | Superiores | scalar_scratch, ms | split, ms | forward, ms | vq, ms | scalar_scratch / forward | split / forward | vq / forward | Puerta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| half_grouped | 32653 | 2502165 | 5000000 | 2497835 | 33.109710 | 26.685843 | 26.931659 | 36.629450 | 1.229397 | 0.990873 | 1.360089 | Pasa (vq ≥ 0.90) |
| half_grouped | 77347 | 2500926 | 5000000 | 2499074 | 32.821154 | 26.647329 | 27.238831 | 36.779961 | 1.204940 | 0.978285 | 1.350277 | Pasa (vq ≥ 0.90) |
| half_periodic | 32653 | 2502165 | 5000000 | 2497835 | 34.362770 | 30.623309 | 29.232865 | 38.139860 | 1.175484 | 1.047564 | 1.304691 | Pasa (vq ≥ 0.90) |
| half_periodic | 77347 | 2500926 | 5000000 | 2499074 | 33.371188 | 29.447616 | 28.137220 | 37.261560 | 1.186016 | 1.046572 | 1.324280 | Pasa (vq ≥ 0.90) |
| half_random | 32653 | 2502165 | 5000000 | 2497835 | 57.657139 | 37.686873 | 35.678215 | 36.892841 | 1.616032 | 1.056299 | 1.034044 | Falla (vq ≥ 1.10) |
| half_random | 77347 | 2500926 | 5000000 | 2499074 | 56.846725 | 37.105820 | 35.960380 | 36.868266 | 1.580815 | 1.031853 | 1.025247 | Falla (vq ≥ 1.10) |
| skew_random | 32653 | 250147 | 9500000 | 249853 | 12.558962 | 13.745396 | 11.708213 | 25.536700 | 1.072663 | 1.173996 | 2.181093 | Pasa (scalar_scratch ≥ 0.90) |
| skew_random | 77347 | 249791 | 9500000 | 250209 | 12.378886 | 14.012645 | 11.917956 | 26.110676 | 1.038675 | 1.175759 | 2.190869 | Pasa (scalar_scratch ≥ 0.90) |
| half_low | 32653 | 5000000 | 5000000 | 0 | 58.637066 | 37.201987 | 35.345863 | 36.668011 | 1.658951 | 1.052513 | 1.037406 | Pasa (vq ≥ 0.90) |
| half_low | 77347 | 5000000 | 5000000 | 0 | 57.925567 | 36.729495 | 35.716454 | 36.356369 | 1.621817 | 1.028363 | 1.017917 | Pasa (vq ≥ 0.90) |
| half_high | 32653 | 0 | 5000000 | 5000000 | 54.366844 | 36.626994 | 35.803647 | 36.127962 | 1.518472 | 1.022996 | 1.009058 | Pasa (vq ≥ 0.90) |
| half_high | 77347 | 0 | 5000000 | 5000000 | 54.564273 | 36.820685 | 36.266191 | 37.471840 | 1.504549 | 1.015290 | 1.033244 | Pasa (vq ≥ 0.90) |

**Filtro fallido.**

- half_random/32653 obtuvo 1.034044 frente a vq, por debajo de 1.10.
- half_random/77347 obtuvo 1.025247 frente a vq, por debajo de 1.10.

## Pérdidas de forward

- half_grouped/32653 perdió frente a split (0.990873).
- half_grouped/77347 perdió frente a split (0.978285).

336 muestras y 384 salidas exactas con calentamientos. 4916 comprobaciones previas de correctitud.

[Diagnóstico separado de fases](phases.md).
