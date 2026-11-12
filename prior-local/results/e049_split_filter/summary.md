# E049 — Separación in situ con ventana preparada

Cada cociente divide la mediana de la referencia por la de split. La puerta usa vq para el 50/50 y scalar_scratch para el 95/5.

| Familia | Semilla | Inferiores | Internos | Superiores | Scalar scratch, ms | Compact scratch, ms | Split, ms | Vqsort, ms | Scalar / split | Compact / split | Vqsort / split | Puerta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| half_grouped | 28729 | 2503142 | 5000000 | 2496858 | 32.938606 | 31.308193 | 26.845863 | 37.271854 | 1.226953 | 1.166220 | 1.388365 | Pasa (vq ≥ 0.90) |
| half_grouped | 80149 | 2500727 | 5000000 | 2499273 | 32.512421 | 31.590752 | 27.029038 | 37.171085 | 1.202870 | 1.168771 | 1.375228 | Pasa (vq ≥ 0.90) |
| half_periodic | 28729 | 2503142 | 5000000 | 2496858 | 31.905418 | 32.928607 | 29.631843 | 37.533373 | 1.076727 | 1.111257 | 1.266657 | Pasa (vq ≥ 0.90) |
| half_periodic | 80149 | 2500727 | 5000000 | 2499273 | 34.385578 | 36.603332 | 32.367660 | 39.559394 | 1.062344 | 1.130861 | 1.222189 | Pasa (vq ≥ 0.90) |
| half_random | 28729 | 2503142 | 5000000 | 2496858 | 58.006086 | 40.693061 | 38.575827 | 36.854461 | 1.503690 | 1.054885 | 0.955377 | Falla (vq ≥ 1.10) |
| half_random | 80149 | 2500727 | 5000000 | 2499273 | 56.660151 | 39.292715 | 37.883757 | 36.667695 | 1.495632 | 1.037192 | 0.967900 | Falla (vq ≥ 1.10) |
| skew_random | 28729 | 250182 | 9500000 | 249818 | 12.578118 | 12.770818 | 13.994505 | 26.320062 | 0.898790 | 0.912559 | 1.880743 | Falla (scalar_scratch ≥ 0.90) |
| skew_random | 80149 | 250118 | 9500000 | 249882 | 14.376586 | 13.612781 | 14.642342 | 26.960997 | 0.981850 | 0.929686 | 1.841304 | Pasa (scalar_scratch ≥ 0.90) |
| half_low | 28729 | 5000000 | 5000000 | 0 | 59.700962 | 41.513482 | 37.360499 | 36.892695 | 1.597970 | 1.111160 | 0.987479 | Pasa (vq ≥ 0.90) |
| half_low | 80149 | 5000000 | 5000000 | 0 | 57.648149 | 40.556454 | 37.375275 | 36.800125 | 1.542414 | 1.085115 | 0.984611 | Pasa (vq ≥ 0.90) |
| half_high | 28729 | 0 | 5000000 | 5000000 | 55.029250 | 38.168859 | 38.348254 | 36.807807 | 1.434987 | 0.995322 | 0.959830 | Pasa (vq ≥ 0.90) |
| half_high | 80149 | 0 | 5000000 | 5000000 | 57.284422 | 38.816987 | 38.567991 | 37.427312 | 1.485284 | 1.006456 | 0.970424 | Pasa (vq ≥ 0.90) |

**Filtro fallido.**

- half_random/28729 obtuvo 0.955377 frente a vq, por debajo de 1.10.
- half_random/80149 obtuvo 0.967900 frente a vq, por debajo de 1.10.
- skew_random/28729 obtuvo 0.898790 frente a scalar_scratch, por debajo de 0.90.

## Pérdidas de split

- half_random/28729 perdió frente a vq (0.955377).
- half_random/80149 perdió frente a vq (0.967900).
- skew_random/28729 perdió frente a scalar_scratch (0.898790), compact_scratch (0.912559).
- skew_random/80149 perdió frente a scalar_scratch (0.981850), compact_scratch (0.929686).
- half_low/28729 perdió frente a vq (0.987479).
- half_low/80149 perdió frente a vq (0.984611).
- half_high/28729 perdió frente a compact_scratch (0.995322), vq (0.959830).
- half_high/80149 perdió frente a vq (0.970424).

336 muestras y 384 salidas exactas con calentamientos. 4916 comprobaciones previas de correctitud.
