# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: local10simd

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 65536 | uniform | 17 | local10simd | 0.168 | simd | 0.208 | 1.241 |
| 65536 | uniform | 83 | local10simd | 0.170 | simd | 0.211 | 1.242 |
| 65536 | uniform | 501 | local10simd | 0.217 | simd | 0.213 | 0.980 |
| 65536 | uniform | 904 | local10simd | 0.168 | simd | 0.207 | 1.238 |
| 65536 | uniform | 7701 | local10simd | 0.232 | simd | 0.211 | 0.911 |
| 100000 | uniform | 17 | local10simd | 0.243 | simd | 0.341 | 1.403 |
| 100000 | uniform | 83 | local10simd | 0.245 | simd | 0.341 | 1.394 |
| 100000 | uniform | 501 | local10simd | 0.242 | simd | 0.331 | 1.368 |
| 100000 | uniform | 904 | local10simd | 0.247 | simd | 0.333 | 1.348 |
| 100000 | uniform | 7701 | local10simd | 0.244 | simd | 0.333 | 1.364 |
| 131072 | uniform | 17 | local10simd | 0.394 | lsd11 | 0.462 | 1.171 |
| 131072 | uniform | 83 | local10simd | 0.462 | simd | 0.461 | 0.998 |
| 131072 | uniform | 501 | local10simd | 0.458 | simd | 0.461 | 1.006 |
| 131072 | uniform | 904 | local10simd | 0.475 | simd | 0.468 | 0.985 |
| 131072 | uniform | 7701 | local10simd | 0.485 | simd | 0.457 | 0.943 |
| 262144 | uniform | 17 | local10simd | 0.994 | simd | 0.982 | 0.987 |
| 262144 | uniform | 83 | local10simd | 1.005 | simd | 0.987 | 0.983 |
| 262144 | uniform | 501 | local10simd | 1.007 | simd | 1.005 | 0.998 |
| 262144 | uniform | 904 | local10simd | 0.988 | simd | 0.983 | 0.994 |
| 262144 | uniform | 7701 | local10simd | 1.018 | simd | 1.007 | 0.990 |
