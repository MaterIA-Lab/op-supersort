# E048 — Filtro de compactación AVX2

Diagnóstico con ventana y cobertura conocidas. Cada cociente divide la mediana de scalar por la de compact.

| Familia | Semilla | Internos | Externos | Scalar, ms | Compact, ms | Scalar / compact | Mínimo | Puerta |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| half_grouped | 23143 | 5000000 | 5000000 | 6.133690 | 4.406295 | 1.392029 | 0.90 | Pasa |
| half_grouped | 58427 | 5000000 | 5000000 | 5.450725 | 3.854976 | 1.413945 | 0.90 | Pasa |
| half_periodic | 23143 | 5000000 | 5000000 | 6.101961 | 7.711284 | 0.791303 | 0.90 | Falla |
| half_periodic | 58427 | 5000000 | 5000000 | 5.447660 | 5.345166 | 1.019175 | 0.90 | Pasa |
| half_random | 23143 | 5000000 | 5000000 | 29.139201 | 11.947032 | 2.439033 | 1.20 | Pasa |
| half_random | 58427 | 5000000 | 5000000 | 29.366857 | 11.980244 | 2.451274 | 1.20 | Pasa |
| skew_grouped | 23143 | 9500000 | 500000 | 5.171664 | 3.603196 | 1.435299 | 0.90 | Pasa |
| skew_grouped | 58427 | 9500000 | 500000 | 6.053480 | 3.793430 | 1.595780 | 0.90 | Pasa |
| skew_periodic | 23143 | 9500000 | 500000 | 5.980383 | 5.679893 | 1.052904 | 0.90 | Pasa |
| skew_periodic | 58427 | 9500000 | 500000 | 6.009498 | 5.725410 | 1.049619 | 0.90 | Pasa |
| skew_random | 23143 | 9500000 | 500000 | 7.924691 | 7.813426 | 1.014240 | 0.95 | Pasa |
| skew_random | 58427 | 9500000 | 500000 | 8.466701 | 7.876222 | 1.074970 | 0.95 | Pasa |
| two_half_random | 23143 | 5000000 | 5000000 | 31.238805 | 12.762360 | 2.447729 | 1.20 | Pasa |
| two_half_random | 58427 | 5000000 | 5000000 | 30.915786 | 12.738725 | 2.426914 | 1.20 | Pasa |
| two_skew_random | 23143 | 9500000 | 500000 | 33.733763 | 11.289591 | 2.988041 | 0.95 | Pasa |
| two_skew_random | 58427 | 9500000 | 500000 | 33.452508 | 10.837187 | 3.086826 | 0.95 | Pasa |
| inside | 23143 | 10000000 | 0 | 4.219186 | 3.490686 | 1.208698 | — | Control |
| inside | 58427 | 10000000 | 0 | 4.066952 | 3.712956 | 1.095341 | — | Control |

**Filtro fallido.**

- half_periodic/23143 obtuvo 0.791303, por debajo de 0.90.

252 muestras y 288 salidas exactas con calentamientos. 2248 comprobaciones previas de correctitud.
