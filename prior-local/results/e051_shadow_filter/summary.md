# E051 — Separación in situ con ventana preparada

Cada cociente divide la mediana de la referencia por la de shadow. La tabla indica la referencia de cada puerta.

| Familia | Semilla | Inferiores | Internos | Superiores | scalar_scratch, ms | forward, ms | shadow, ms | vq, ms | scalar_scratch / shadow | forward / shadow | vq / shadow | Puerta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| half_grouped | 35911 | 2502044 | 5000000 | 2497956 | 32.446013 | 27.308022 | 34.249060 | 36.785653 | 0.947355 | 0.797336 | 1.074063 | Pasa (vq ≥ 0.90) |
| half_grouped | 88493 | 2497914 | 5000000 | 2502086 | 32.837614 | 26.630808 | 33.493938 | 36.473151 | 0.980405 | 0.795093 | 1.088948 | Pasa (vq ≥ 0.90) |
| half_periodic | 35911 | 2502044 | 5000000 | 2497956 | 32.104717 | 28.178287 | 33.837431 | 36.641283 | 0.948793 | 0.832755 | 1.082862 | Pasa (vq ≥ 0.90) |
| half_periodic | 88493 | 2497914 | 5000000 | 2502086 | 31.330102 | 28.090541 | 33.783130 | 36.449718 | 0.927389 | 0.831496 | 1.078933 | Pasa (vq ≥ 0.90) |
| half_random | 35911 | 2502044 | 5000000 | 2497956 | 56.105859 | 35.405831 | 33.820192 | 36.371222 | 1.658946 | 1.046884 | 1.075429 | Falla (vq ≥ 1.10) |
| half_random | 88493 | 2497914 | 5000000 | 2502086 | 55.869859 | 34.923549 | 33.214791 | 35.903029 | 1.682078 | 1.051446 | 1.080935 | Falla (vq ≥ 1.10) |
| skew_random | 35911 | 250145 | 9500000 | 249855 | 12.413702 | 12.065461 | 15.315949 | 25.035973 | 0.810508 | 0.787771 | 1.634634 | Falla (scalar_scratch ≥ 0.90) |
| skew_random | 88493 | 249950 | 9500000 | 250050 | 12.514532 | 11.849529 | 14.978980 | 24.605722 | 0.835473 | 0.791077 | 1.642683 | Falla (scalar_scratch ≥ 0.90) |
| half_low | 35911 | 5000000 | 5000000 | 0 | 57.806921 | 35.163112 | 33.830374 | 36.049758 | 1.708728 | 1.039395 | 1.065603 | Pasa (vq ≥ 0.90) |
| half_low | 88493 | 5000000 | 5000000 | 0 | 58.213650 | 35.569351 | 33.531145 | 36.756526 | 1.736107 | 1.060785 | 1.096191 | Pasa (vq ≥ 0.90) |
| half_high | 35911 | 0 | 5000000 | 5000000 | 55.037606 | 37.191163 | 35.199116 | 37.309200 | 1.563608 | 1.056594 | 1.059947 | Pasa (vq ≥ 0.90) |
| half_high | 88493 | 0 | 5000000 | 5000000 | 57.179727 | 37.878261 | 35.416190 | 38.280979 | 1.614508 | 1.069518 | 1.080889 | Pasa (vq ≥ 0.90) |
| half_repeat | 35911 | 0 | 5000000 | 5000000 | 32.712328 | 14.832849 | 13.571935 | 15.738631 | 2.410292 | 1.092906 | 1.159645 | Pasa (forward ≥ 0.90) |
| half_repeat | 88493 | 0 | 5000000 | 5000000 | 34.113290 | 15.390050 | 14.048225 | 19.241673 | 2.428299 | 1.095516 | 1.369687 | Pasa (forward ≥ 0.90) |

**Filtro fallido.**

- half_random/35911 obtuvo 1.075429 frente a vq, por debajo de 1.10.
- half_random/88493 obtuvo 1.080935 frente a vq, por debajo de 1.10.
- skew_random/35911 obtuvo 0.810508 frente a scalar_scratch, por debajo de 0.90.
- skew_random/88493 obtuvo 0.835473 frente a scalar_scratch, por debajo de 0.90.

## Pérdidas de shadow

- half_grouped/35911 perdió frente a scalar_scratch (0.947355), forward (0.797336).
- half_grouped/88493 perdió frente a scalar_scratch (0.980405), forward (0.795093).
- half_periodic/35911 perdió frente a scalar_scratch (0.948793), forward (0.832755).
- half_periodic/88493 perdió frente a scalar_scratch (0.927389), forward (0.831496).
- skew_random/35911 perdió frente a scalar_scratch (0.810508), forward (0.787771).
- skew_random/88493 perdió frente a scalar_scratch (0.835473), forward (0.791077).

392 muestras y 448 salidas exactas con calentamientos. 4916 comprobaciones previas de correctitud.

[Diagnóstico separado de fases](phases.md).
