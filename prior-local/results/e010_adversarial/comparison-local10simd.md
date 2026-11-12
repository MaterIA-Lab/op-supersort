# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: local10simd

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 100000 | dense16 | 17 | local10simd | 0.541 | simd | 0.356 | 0.658 |
| 100000 | dense16 | 83 | local10simd | 0.474 | simd | 0.367 | 0.774 |
| 100000 | dense16 | 501 | local10simd | 0.468 | simd | 0.361 | 0.772 |
| 100000 | equal | 17 | local10simd | 0.110 | simd | 0.004 | 0.039 |
| 100000 | equal | 83 | local10simd | 0.111 | simd | 0.004 | 0.039 |
| 100000 | equal | 501 | local10simd | 0.112 | simd | 0.004 | 0.038 |
| 100000 | few | 17 | local10simd | 0.272 | simd | 0.076 | 0.281 |
| 100000 | few | 83 | local10simd | 0.274 | simd | 0.079 | 0.287 |
| 100000 | few | 501 | local10simd | 0.345 | simd | 0.084 | 0.245 |
| 100000 | reverse | 17 | local10simd | 0.254 | pdq | 0.102 | 0.401 |
| 100000 | reverse | 83 | local10simd | 0.340 | pdq | 0.105 | 0.307 |
| 100000 | reverse | 501 | local10simd | 0.257 | pdq | 0.101 | 0.395 |
| 100000 | skew | 17 | local10simd | 0.561 | simd | 0.360 | 0.642 |
| 100000 | skew | 83 | local10simd | 0.633 | simd | 0.369 | 0.583 |
| 100000 | skew | 501 | local10simd | 0.635 | simd | 0.366 | 0.577 |
| 100000 | sorted | 17 | local10simd | 0.257 | pdq | 0.044 | 0.170 |
| 100000 | sorted | 83 | local10simd | 0.326 | pdq | 0.055 | 0.168 |
| 100000 | sorted | 501 | local10simd | 0.253 | pdq | 0.044 | 0.173 |
