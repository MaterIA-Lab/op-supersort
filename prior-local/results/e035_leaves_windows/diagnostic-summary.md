# E035 — diagnóstico de hojas aisladas

No es un ranking de sorters completos. 512 hojas por muestra; 15 muestras por longitud más calentamiento. Copia, reserva y comprobación fuera del tiempo de este microbenchmark.

| longitud | mediana ns/hoja | mínimo | máximo |
|---:|---:|---:|---:|
| 31 | 33.789 | 33.398 | 41.016 |
| 32 | 33.594 | 33.203 | 34.180 |
| 33 | 53.516 | 52.930 | 53.906 |
| 63 | 53.906 | 53.320 | 54.492 |
| 64 | 53.711 | 53.320 | 54.102 |
| 65 | 99.805 | 98.242 | 113.867 |
| 95 | 100.977 | 99.414 | 113.086 |
| 96 | 100.586 | 99.609 | 101.758 |
| 97 | 100.781 | 99.414 | 108.984 |
| 111 | 101.172 | 100.000 | 102.734 |
| 112 | 100.781 | 99.609 | 124.805 |
| 113 | 107.227 | 99.609 | 138.086 |
| 127 | 100.977 | 99.805 | 103.516 |
| 128 | 101.367 | 99.609 | 178.906 |
| 129 | 320.898 | 315.625 | 324.023 |
| 159 | 327.539 | 323.633 | 377.344 |
| 160 | 326.367 | 324.414 | 349.219 |
| 161 | 328.516 | 324.023 | 364.844 |
| 255 | 321.680 | 318.555 | 340.039 |
| 256 | 336.523 | 332.227 | 436.133 |
| 257 | 493.750 | 484.766 | 895.508 |

Ratio 129/128: 3.166.

En 129000 claves, cuatro entradas: K1024 tiene 402–428 buckets >128; K1280 tiene 5–9. El corpus de ocupación es idéntico entre sistemas por construcción. Compatible con la explicación por escalones, sin aislamiento causal de scatter/layout en el sorter completo.

Comprobación exacta: 21 longitudes * 16 rondas * 512 hojas = 172032 hojas por sistema; 315 muestras temporizadas. Fuente exacta y commit de dependencia en esta carpeta.
