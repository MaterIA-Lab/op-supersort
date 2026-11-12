# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 16384 | uniform | 991 | local8simd | 0.065 | simd | 0.047 | 0.718 |
| 16384 | uniform | 123456 | local8simd | 0.052 | simd | 0.047 | 0.899 |
| 16384 | uniform | 987654321 | local8simd | 0.055 | simd | 0.045 | 0.814 |
| 65536 | uniform | 991 | local10simdhot | 0.166 | simd | 0.213 | 1.285 |
| 65536 | uniform | 123456 | local10simd | 0.165 | simd | 0.214 | 1.296 |
| 65536 | uniform | 987654321 | local10simdhot | 0.216 | simd | 0.218 | 1.009 |
| 100000 | uniform | 991 | local10simd | 0.326 | simd | 0.349 | 1.071 |
| 100000 | uniform | 123456 | local10simdhot | 0.302 | simd | 0.345 | 1.140 |
| 100000 | uniform | 987654321 | local10simd | 0.234 | simd | 0.342 | 1.459 |
| 262144 | uniform | 991 | local12simdhot | 0.907 | simd | 0.962 | 1.060 |
| 262144 | uniform | 123456 | local12simdhot | 0.931 | simd | 0.966 | 1.037 |
| 262144 | uniform | 987654321 | local12simdhot | 0.906 | simd | 0.970 | 1.071 |
| 1000000 | uniform | 991 | local12simdhot | 4.427 | simd | 4.090 | 0.924 |
| 1000000 | uniform | 123456 | local14simd | 4.570 | simd | 4.138 | 0.905 |
| 1000000 | uniform | 987654321 | local14simd | 4.516 | simd | 4.117 | 0.912 |
