# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: predict10s4

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 80000 | splitmix | 271 | predict10s4 | 0.250 | simd | 0.284 | 1.135 |
| 80000 | splitmix | 811 | predict10s4 | 0.256 | simd | 0.291 | 1.138 |
| 80000 | splitmix | 1601 | predict10s4 | 0.179 | lsd11 | 0.277 | 1.548 |
| 80000 | splitmix | 4099 | predict10s4 | 0.277 | simd | 0.281 | 1.013 |
| 80000 | splitmix | 65537 | predict10s4 | 0.270 | simd | 0.283 | 1.051 |
| 80000 | uniform | 271 | predict10s4 | 0.181 | lsd11 | 0.276 | 1.528 |
| 80000 | uniform | 811 | predict10s4 | 0.180 | lsd11 | 0.276 | 1.536 |
| 80000 | uniform | 1601 | predict10s4 | 0.182 | lsd11 | 0.277 | 1.521 |
| 80000 | uniform | 4099 | predict10s4 | 0.180 | lsd11 | 0.275 | 1.528 |
| 80000 | uniform | 65537 | predict10s4 | 0.182 | simd | 0.276 | 1.517 |
| 100000 | splitmix | 271 | predict10s4 | 0.288 | simd | 0.365 | 1.267 |
| 100000 | splitmix | 811 | predict10s4 | 0.298 | simd | 0.358 | 1.203 |
| 100000 | splitmix | 1601 | predict10s4 | 0.279 | simd | 0.363 | 1.303 |
| 100000 | splitmix | 4099 | predict10s4 | 0.275 | simd | 0.358 | 1.299 |
| 100000 | splitmix | 65537 | predict10s4 | 0.281 | simd | 0.362 | 1.289 |
| 100000 | uniform | 271 | predict10s4 | 0.320 | simd | 0.363 | 1.133 |
| 100000 | uniform | 811 | predict10s4 | 0.199 | lsd11 | 0.347 | 1.745 |
| 100000 | uniform | 1601 | predict10s4 | 0.200 | lsd11 | 0.349 | 1.747 |
| 100000 | uniform | 4099 | predict10s4 | 0.206 | lsd11 | 0.347 | 1.689 |
| 100000 | uniform | 65537 | predict10s4 | 0.200 | lsd11 | 0.347 | 1.735 |
| 120000 | splitmix | 271 | predict10s4 | 0.352 | simd | 0.437 | 1.241 |
| 120000 | splitmix | 811 | predict10s4 | 0.367 | simd | 0.428 | 1.164 |
| 120000 | splitmix | 1601 | predict10s4 | 0.346 | simd | 0.429 | 1.241 |
| 120000 | splitmix | 4099 | predict10s4 | 0.258 | lsd11 | 0.420 | 1.630 |
| 120000 | splitmix | 65537 | predict10s4 | 0.344 | simd | 0.434 | 1.261 |
| 120000 | uniform | 271 | predict10s4 | 0.263 | lsd11 | 0.420 | 1.595 |
| 120000 | uniform | 811 | predict10s4 | 0.266 | lsd11 | 0.420 | 1.580 |
| 120000 | uniform | 1601 | predict10s4 | 0.388 | simd | 0.442 | 1.140 |
| 120000 | uniform | 4099 | predict10s4 | 0.264 | lsd11 | 0.416 | 1.576 |
| 120000 | uniform | 65537 | predict10s4 | 0.268 | lsd11 | 0.418 | 1.561 |
