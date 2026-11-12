# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | mejor local | ms | mejor referencia | ms | referencia / local |
|---:|---|---:|---|---:|---|---:|---:|
| 100000 | uniform | 42 | local10simd | 0.305 | simd | 0.359 | 1.179 |
| 100000 | uniform | 137 | local10simd | 0.302 | simd | 0.369 | 1.223 |
| 100000 | uniform | 2026 | local10simd | 0.302 | simd | 0.374 | 1.238 |
| 1000000 | uniform | 42 | local8c32 | 5.527 | simd | 4.194 | 0.759 |
| 1000000 | uniform | 137 | local8c32 | 5.448 | simd | 4.157 | 0.763 |
| 1000000 | uniform | 2026 | local8c32 | 5.595 | simd | 4.397 | 0.786 |
| 10000000 | uniform | 42 | local8c32 | 60.253 | simd | 51.437 | 0.854 |
| 10000000 | uniform | 137 | local8c32 | 60.115 | simd | 50.854 | 0.846 |
| 10000000 | uniform | 2026 | local8c32 | 59.563 | simd | 50.262 | 0.844 |
