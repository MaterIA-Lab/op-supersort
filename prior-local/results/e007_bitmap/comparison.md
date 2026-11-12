# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 100000 | uniform | 42 | local8c32 | 1.041 | simd | 0.356 | 0.342 |
| 100000 | uniform | 137 | local8c32 | 1.103 | simd | 0.356 | 0.323 |
| 100000 | uniform | 2026 | local8c32 | 0.994 | simd | 0.351 | 0.353 |
| 1000000 | uniform | 42 | local8c32 | 5.550 | simd | 4.142 | 0.746 |
| 1000000 | uniform | 137 | local8c32 | 5.452 | simd | 4.176 | 0.766 |
| 1000000 | uniform | 2026 | local8c32 | 5.515 | simd | 4.163 | 0.755 |
| 10000000 | uniform | 42 | local8c32 | 59.867 | simd | 49.383 | 0.825 |
| 10000000 | uniform | 137 | local8c32 | 58.638 | simd | 51.332 | 0.875 |
| 10000000 | uniform | 2026 | local8c32 | 58.047 | simd | 50.004 | 0.861 |
