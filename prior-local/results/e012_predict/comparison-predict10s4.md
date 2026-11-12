# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: predict10s4

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 65536 | uniform | 17 | predict10s4 | 0.141 | simd | 0.212 | 1.507 |
| 65536 | uniform | 83 | predict10s4 | 0.140 | simd | 0.211 | 1.503 |
| 65536 | uniform | 501 | predict10s4 | 0.142 | simd | 0.216 | 1.526 |
| 65536 | uniform | 904 | predict10s4 | 0.155 | simd | 0.214 | 1.380 |
| 65536 | uniform | 7701 | predict10s4 | 0.140 | simd | 0.211 | 1.504 |
| 100000 | uniform | 17 | predict10s4 | 0.206 | simd | 0.344 | 1.667 |
| 100000 | uniform | 83 | predict10s4 | 0.202 | simd | 0.341 | 1.686 |
| 100000 | uniform | 501 | predict10s4 | 0.209 | simd | 0.338 | 1.620 |
| 100000 | uniform | 904 | predict10s4 | 0.202 | simd | 0.333 | 1.650 |
| 100000 | uniform | 7701 | predict10s4 | 0.207 | simd | 0.337 | 1.632 |
| 131072 | uniform | 17 | predict10s4 | 0.423 | lsd11 | 0.468 | 1.105 |
| 131072 | uniform | 83 | predict10s4 | 0.428 | simd | 0.466 | 1.087 |
| 131072 | uniform | 501 | predict10s4 | 0.426 | simd | 0.471 | 1.106 |
| 131072 | uniform | 904 | predict10s4 | 0.427 | simd | 0.470 | 1.099 |
| 131072 | uniform | 7701 | predict10s4 | 0.439 | simd | 0.465 | 1.059 |
| 262144 | uniform | 17 | predict10s4 | 1.053 | simd | 0.995 | 0.945 |
| 262144 | uniform | 83 | predict10s4 | 1.065 | simd | 0.999 | 0.939 |
| 262144 | uniform | 501 | predict10s4 | 1.044 | simd | 0.989 | 0.947 |
| 262144 | uniform | 904 | predict10s4 | 1.060 | simd | 0.990 | 0.934 |
| 262144 | uniform | 7701 | predict10s4 | 1.152 | simd | 1.014 | 0.880 |
| 1000000 | uniform | 17 | predict10s4 | 6.120 | simd | 4.166 | 0.681 |
| 1000000 | uniform | 83 | predict10s4 | 5.967 | simd | 4.194 | 0.703 |
| 1000000 | uniform | 501 | predict10s4 | 5.926 | simd | 4.175 | 0.704 |
| 1000000 | uniform | 904 | predict10s4 | 6.071 | simd | 4.282 | 0.705 |
| 1000000 | uniform | 7701 | predict10s4 | 6.263 | simd | 4.247 | 0.678 |
| 10000000 | uniform | 17 | predict10s4 | 70.252 | simd | 51.092 | 0.727 |
| 10000000 | uniform | 83 | predict10s4 | 70.655 | simd | 52.334 | 0.741 |
| 10000000 | uniform | 501 | predict10s4 | 71.174 | simd | 52.179 | 0.733 |
| 10000000 | uniform | 904 | predict10s4 | 70.778 | simd | 52.256 | 0.738 |
| 10000000 | uniform | 7701 | predict10s4 | 70.485 | simd | 51.208 | 0.727 |
