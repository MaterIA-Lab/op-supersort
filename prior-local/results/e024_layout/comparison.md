# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 65536 | splitmix | 271 | predict10raw | 0.141 | simd | 0.214 | 1.521 |
| 65536 | splitmix | 811 | predict10shiftraw | 0.143 | simd | 0.216 | 1.516 |
| 65536 | splitmix | 1601 | predict10raw | 0.139 | simd | 0.215 | 1.543 |
| 65536 | uniform | 271 | predict10raw | 0.139 | simd | 0.220 | 1.581 |
| 65536 | uniform | 811 | predict10raw | 0.133 | simd | 0.215 | 1.614 |
| 65536 | uniform | 1601 | predict10raw | 0.139 | vq | 0.217 | 1.568 |
| 80000 | splitmix | 271 | predict10raw | 0.177 | vq | 0.270 | 1.524 |
| 80000 | splitmix | 811 | predict10shiftraw | 0.179 | simd | 0.272 | 1.518 |
| 80000 | splitmix | 1601 | predict10oddraw | 0.178 | vq | 0.268 | 1.503 |
| 80000 | uniform | 271 | predict10oddraw | 0.178 | vq | 0.269 | 1.511 |
| 80000 | uniform | 811 | predict10oddraw | 0.180 | vq | 0.273 | 1.520 |
| 80000 | uniform | 1601 | predict10raw | 0.178 | vq | 0.269 | 1.509 |
| 100000 | splitmix | 271 | predict10raw | 0.195 | vq | 0.342 | 1.752 |
| 100000 | splitmix | 811 | predict10shiftraw | 0.204 | vq | 0.345 | 1.695 |
| 100000 | splitmix | 1601 | predict10raw | 0.204 | vq | 0.341 | 1.669 |
| 100000 | uniform | 271 | predict10raw | 0.201 | vq | 0.341 | 1.698 |
| 100000 | uniform | 811 | predict10oddraw | 0.200 | vq | 0.343 | 1.711 |
| 100000 | uniform | 1601 | predict10oddraw | 0.194 | vq | 0.341 | 1.754 |
| 120000 | splitmix | 271 | predict10shiftraw | 0.258 | vq | 0.418 | 1.619 |
| 120000 | splitmix | 811 | predict10shiftraw | 0.259 | vq | 0.415 | 1.599 |
| 120000 | splitmix | 1601 | predict10shiftraw | 0.253 | vq | 0.419 | 1.656 |
| 120000 | uniform | 271 | predict10shiftraw | 0.243 | vq | 0.417 | 1.714 |
| 120000 | uniform | 811 | predict10oddraw | 0.256 | vq | 0.416 | 1.627 |
| 120000 | uniform | 1601 | predict10oddraw | 0.250 | vq | 0.416 | 1.665 |
| 131072 | splitmix | 271 | predict10shiftraw | 0.340 | vq | 0.458 | 1.347 |
| 131072 | splitmix | 811 | predict10shiftraw | 0.338 | vq | 0.458 | 1.355 |
| 131072 | splitmix | 1601 | predict10shiftraw | 0.337 | vq | 0.465 | 1.378 |
| 131072 | uniform | 271 | predict10shift | 0.348 | vq | 0.457 | 1.314 |
| 131072 | uniform | 811 | predict10shiftraw | 0.337 | vq | 0.458 | 1.358 |
| 131072 | uniform | 1601 | predict10shiftraw | 0.336 | vq | 0.458 | 1.362 |
