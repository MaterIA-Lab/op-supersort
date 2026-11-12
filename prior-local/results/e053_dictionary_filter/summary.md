# E053 — Filtro del diccionario exacto

Cada cociente divide la mediana de la referencia por la de striped. El sobrecoste es la mediana de striped menos la de vqsort.

| Familia | Semilla | Single, ms | Striped, ms | Vqsort, ms | Single / striped | Vqsort / striped | Striped − vqsort, ms | Ruta | Examinadas | Propuestas | Puerta |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| few | 40559 | 7.756500 | 7.354900 | 11.297620 | 1.054603 | 1.536067 | -3.942720 | counted | 10000000 | 16 | Pasa |
| few | 89119 | 8.909121 | 7.742133 | 12.541962 | 1.150732 | 1.619962 | -4.799829 | counted | 10000000 | 16 | Pasa |
| few_permute | 40559 | 7.141712 | 7.505150 | 12.505244 | 0.951575 | 1.666222 | -5.000094 | counted | 10000000 | 16 | Pasa |
| few_permute | 89119 | 8.408546 | 8.120679 | 13.254312 | 1.035449 | 1.632168 | -5.133633 | counted | 10000000 | 16 | Pasa |
| few_dominant | 40559 | 17.159582 | 9.225090 | 10.641530 | 1.860099 | 1.153542 | -1.416440 | counted | 10000000 | 16 | Pasa |
| few_dominant | 89119 | 17.089832 | 8.337454 | 9.777532 | 2.049766 | 1.172724 | -1.440078 | counted | 10000000 | 16 | Pasa |
| few_powers | 40559 | 13.191855 | 14.383099 | 13.442744 | 0.917178 | 0.934621 | +0.940355 | collision | 0 | 16 | Pasa |
| few_powers | 89119 | 12.008177 | 11.704048 | 11.453481 | 1.025985 | 0.978591 | +0.250567 | collision | 0 | 16 | Pasa |
| uniform | 40559 | 48.794889 | 48.752088 | 48.679113 | 1.000878 | 0.998503 | +0.072975 | bypass | 0 | 17 | Pasa |
| uniform | 89119 | 49.462805 | 49.654023 | 50.228265 | 0.996149 | 1.011565 | -0.574242 | bypass | 0 | 17 | Pasa |
| mixed | 40559 | 38.411217 | 38.033403 | 38.398473 | 1.009934 | 1.009599 | -0.365070 | bypass | 0 | 17 | Pasa |
| mixed | 89119 | 36.702800 | 37.460172 | 37.556484 | 0.979782 | 1.002571 | -0.096312 | bypass | 0 | 17 | Pasa |
| equal | 40559 | 1.680517 | 1.606358 | 1.494250 | 1.046166 | 0.930210 | +0.112108 | bypass | 0 | 1 | Pasa |
| equal | 89119 | 1.756288 | 1.625815 | 1.667613 | 1.080251 | 1.025709 | -0.041798 | bypass | 0 | 1 | Pasa |
| early_unknown | 40559 | 12.258804 | 10.632109 | 10.812835 | 1.152998 | 1.016998 | -0.180726 | reject | 4 | 16 | Pasa |
| early_unknown | 89119 | 11.608551 | 12.177883 | 11.815599 | 0.953249 | 0.970251 | +0.362284 | reject | 4 | 16 | Pasa |
| late_unknown | 40559 | 16.003035 | 16.307193 | 11.637755 | 0.981348 | 0.713658 | +4.669438 | reject | 10000000 | 16 | Pasa |
| late_unknown | 89119 | 16.488001 | 14.983362 | 11.634029 | 1.100421 | 0.776463 | +3.349333 | reject | 10000000 | 16 | Pasa |

**Filtro superado.**


## Pérdidas de striped

- few_permute/40559 perdió frente a single (0.951575).
- few_powers/40559 perdió frente a single (0.917178), vq (0.934621).
- few_powers/89119 perdió frente a vq (0.978591).
- uniform/40559 perdió frente a vq (0.998503).
- uniform/89119 perdió frente a single (0.996149).
- mixed/89119 perdió frente a single (0.979782).
- equal/40559 perdió frente a vq (0.930210).
- early_unknown/89119 perdió frente a single (0.953249), vq (0.970251).
- late_unknown/40559 perdió frente a single (0.981348), vq (0.713658).
- late_unknown/89119 perdió frente a vq (0.776463).

378 muestras y 432 salidas exactas con calentamientos. 270 comprobaciones previas de correctitud.
