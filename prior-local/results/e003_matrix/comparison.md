# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 1000000 | dense16 | 42 | local12 | 5.486 | ska | 4.670 | 0.851 |
| 1000000 | dense16 | 137 | local10 | 5.457 | ska | 4.497 | 0.824 |
| 1000000 | dense16 | 2026 | local12 | 5.320 | ska | 4.462 | 0.839 |
| 1000000 | equal | 42 | local8 | 4.277 | pdq | 0.366 | 0.086 |
| 1000000 | equal | 137 | local8 | 4.108 | pdq | 0.365 | 0.089 |
| 1000000 | equal | 2026 | local10 | 4.204 | pdq | 0.378 | 0.090 |
| 1000000 | few | 42 | local10 | 4.858 | ska | 2.476 | 0.510 |
| 1000000 | few | 137 | local8 | 4.789 | ska | 2.408 | 0.503 |
| 1000000 | few | 2026 | local8 | 4.789 | ska | 2.490 | 0.520 |
| 1000000 | reverse | 42 | local8 | 4.465 | pdq | 1.001 | 0.224 |
| 1000000 | reverse | 137 | local8 | 4.479 | pdq | 1.044 | 0.233 |
| 1000000 | reverse | 2026 | local8 | 4.402 | pdq | 1.019 | 0.231 |
| 1000000 | skew | 42 | local8 | 6.470 | ska | 6.663 | 1.030 |
| 1000000 | skew | 137 | local12 | 6.361 | ska | 6.660 | 1.047 |
| 1000000 | skew | 2026 | local8 | 6.664 | ska | 6.739 | 1.011 |
| 1000000 | sorted | 42 | local8 | 4.391 | pdq | 0.544 | 0.124 |
| 1000000 | sorted | 137 | local8 | 4.590 | pdq | 0.527 | 0.115 |
| 1000000 | sorted | 2026 | local8 | 4.473 | pdq | 0.477 | 0.107 |
| 1000000 | uniform | 42 | local8 | 6.339 | lsd11buf | 7.849 | 1.238 |
| 1000000 | uniform | 137 | local8 | 6.576 | lsd11 | 7.505 | 1.141 |
| 1000000 | uniform | 2026 | local8 | 6.254 | lsd11 | 8.469 | 1.354 |
| 10000000 | dense16 | 42 | local8 | 74.897 | ska | 34.606 | 0.462 |
| 10000000 | dense16 | 137 | local8 | 75.671 | ska | 35.405 | 0.468 |
| 10000000 | dense16 | 2026 | local8 | 74.533 | ska | 34.034 | 0.457 |
| 10000000 | equal | 42 | local8 | 46.928 | pdq | 4.291 | 0.091 |
| 10000000 | equal | 137 | local8 | 45.003 | pdq | 5.317 | 0.118 |
| 10000000 | equal | 2026 | local8 | 43.830 | pdq | 4.512 | 0.103 |
| 10000000 | few | 42 | local8 | 50.466 | ska | 27.329 | 0.542 |
| 10000000 | few | 137 | local8 | 49.440 | ska | 28.064 | 0.568 |
| 10000000 | few | 2026 | local10 | 50.729 | ska | 27.388 | 0.540 |
| 10000000 | reverse | 42 | local12 | 41.838 | pdq | 12.008 | 0.287 |
| 10000000 | reverse | 137 | local12 | 43.988 | pdq | 11.880 | 0.270 |
| 10000000 | reverse | 2026 | local12 | 44.204 | pdq | 12.325 | 0.279 |
| 10000000 | skew | 42 | local8 | 80.999 | ska | 62.456 | 0.771 |
| 10000000 | skew | 137 | local8 | 83.031 | ska | 63.491 | 0.765 |
| 10000000 | skew | 2026 | local8 | 80.486 | ska | 58.529 | 0.727 |
| 10000000 | sorted | 42 | local12 | 42.087 | pdq | 5.367 | 0.128 |
| 10000000 | sorted | 137 | local12 | 42.235 | pdq | 5.150 | 0.122 |
| 10000000 | sorted | 2026 | local12 | 41.301 | pdq | 5.317 | 0.129 |
| 10000000 | uniform | 42 | local12 | 63.608 | lsd8 | 98.404 | 1.547 |
| 10000000 | uniform | 137 | local12 | 63.926 | lsd8 | 100.421 | 1.571 |
| 10000000 | uniform | 2026 | local12 | 65.441 | lsd8 | 98.802 | 1.510 |
