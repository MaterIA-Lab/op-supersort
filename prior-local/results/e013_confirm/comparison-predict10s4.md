# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: predict10s4

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 80000 | splitmix | 271 | predict10s4 | 0.269 | simd | 0.289 | 1.076 |
| 80000 | splitmix | 811 | predict10s4 | 0.258 | simd | 0.289 | 1.120 |
| 80000 | splitmix | 1601 | predict10s4 | 0.273 | simd | 0.285 | 1.045 |
| 80000 | splitmix | 4099 | predict10s4 | 0.262 | simd | 0.289 | 1.101 |
| 80000 | splitmix | 65537 | predict10s4 | 0.265 | simd | 0.290 | 1.094 |
| 80000 | uniform | 271 | predict10s4 | 0.272 | simd | 0.283 | 1.041 |
| 80000 | uniform | 811 | predict10s4 | 0.188 | lsd11 | 0.277 | 1.473 |
| 80000 | uniform | 1601 | predict10s4 | 0.185 | lsd11 | 0.279 | 1.503 |
| 80000 | uniform | 4099 | predict10s4 | 0.256 | simd | 0.285 | 1.114 |
| 80000 | uniform | 65537 | predict10s4 | 0.189 | lsd11 | 0.282 | 1.494 |
| 100000 | splitmix | 271 | predict10s4 | 0.299 | simd | 0.366 | 1.226 |
| 100000 | splitmix | 811 | predict10s4 | 0.286 | simd | 0.360 | 1.258 |
| 100000 | splitmix | 1601 | predict10s4 | 0.294 | simd | 0.364 | 1.237 |
| 100000 | splitmix | 4099 | predict10s4 | 0.285 | simd | 0.354 | 1.242 |
| 100000 | splitmix | 65537 | predict10s4 | 0.286 | simd | 0.358 | 1.249 |
| 100000 | uniform | 271 | predict10s4 | 0.205 | lsd11 | 0.347 | 1.696 |
| 100000 | uniform | 811 | predict10s4 | 0.204 | lsd11 | 0.346 | 1.696 |
| 100000 | uniform | 1601 | predict10s4 | 0.209 | lsd11 | 0.347 | 1.663 |
| 100000 | uniform | 4099 | predict10s4 | 0.208 | lsd11 | 0.346 | 1.661 |
| 100000 | uniform | 65537 | predict10s4 | 0.284 | simd | 0.363 | 1.275 |
| 120000 | splitmix | 271 | predict10s4 | 0.374 | simd | 0.440 | 1.177 |
| 120000 | splitmix | 811 | predict10s4 | 0.363 | simd | 0.436 | 1.203 |
| 120000 | splitmix | 1601 | predict10s4 | 0.270 | lsd11 | 0.420 | 1.560 |
| 120000 | splitmix | 4099 | predict10s4 | 0.347 | simd | 0.442 | 1.271 |
| 120000 | splitmix | 65537 | predict10s4 | 0.382 | simd | 0.435 | 1.140 |
| 120000 | uniform | 271 | predict10s4 | 0.278 | lsd11 | 0.425 | 1.528 |
| 120000 | uniform | 811 | predict10s4 | 0.281 | lsd11 | 0.427 | 1.520 |
| 120000 | uniform | 1601 | predict10s4 | 0.269 | lsd11 | 0.422 | 1.572 |
| 120000 | uniform | 4099 | predict10s4 | 0.281 | lsd11 | 0.425 | 1.510 |
| 120000 | uniform | 65537 | predict10s4 | 0.282 | lsd11 | 0.423 | 1.502 |
