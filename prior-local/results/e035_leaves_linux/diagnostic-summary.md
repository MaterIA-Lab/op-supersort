# E035 — diagnóstico de hojas aisladas

No es un ranking de sorters completos. 512 hojas por muestra; 15 muestras por longitud más calentamiento. Copia, reserva y comprobación fuera del tiempo de este microbenchmark.

| longitud | mediana ns/hoja | mínimo | máximo |
|---:|---:|---:|---:|
| 31 | 29.449 | 27.883 | 45.201 |
| 32 | 29.156 | 28.256 | 40.211 |
| 33 | 48.078 | 45.926 | 88.467 |
| 63 | 48.078 | 46.395 | 202.309 |
| 64 | 48.373 | 46.180 | 94.316 |
| 65 | 91.519 | 90.129 | 133.100 |
| 95 | 105.488 | 93.494 | 153.393 |
| 96 | 97.701 | 93.885 | 135.938 |
| 97 | 97.250 | 92.769 | 136.055 |
| 111 | 106.586 | 92.811 | 137.385 |
| 112 | 98.387 | 93.926 | 137.111 |
| 113 | 118.404 | 93.240 | 213.619 |
| 127 | 103.670 | 92.848 | 142.021 |
| 128 | 97.486 | 93.180 | 139.322 |
| 129 | 327.955 | 301.303 | 513.359 |
| 159 | 315.941 | 286.471 | 497.686 |
| 160 | 304.826 | 284.318 | 520.600 |
| 161 | 323.963 | 301.695 | 565.527 |
| 255 | 323.082 | 310.029 | 494.691 |
| 256 | 429.453 | 409.807 | 783.814 |
| 257 | 573.705 | 507.391 | 985.605 |

Ratio 129/128: 3.364.

En 129000 claves, cuatro entradas: K1024 tiene 402–428 buckets >128; K1280 tiene 5–9. El corpus de ocupación es idéntico entre sistemas por construcción. Compatible con la explicación por escalones, sin aislamiento causal de scatter/layout en el sorter completo.

Comprobación exacta: 21 longitudes * 16 rondas * 512 hojas = 172032 hojas por sistema; 315 muestras temporizadas. Fuente exacta y commit de dependencia en esta carpeta.
