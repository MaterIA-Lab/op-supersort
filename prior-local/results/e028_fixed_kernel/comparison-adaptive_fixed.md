# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: adaptive_fixed

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 70000 | splitmix | 1009 | adaptive_fixed | 0.156 | vq | 0.229 | 1.463 |
| 70000 | splitmix | 12347 | adaptive_fixed | 0.155 | vq | 0.231 | 1.488 |
| 70000 | splitmix | 99991 | adaptive_fixed | 0.153 | vq | 0.231 | 1.503 |
| 70000 | uniform | 1009 | adaptive_fixed | 0.152 | vq | 0.227 | 1.494 |
| 70000 | uniform | 12347 | adaptive_fixed | 0.154 | vq | 0.229 | 1.485 |
| 70000 | uniform | 99991 | adaptive_fixed | 0.154 | vq | 0.227 | 1.473 |
| 100000 | splitmix | 1009 | adaptive_fixed | 0.201 | vq | 0.334 | 1.659 |
| 100000 | splitmix | 12347 | adaptive_fixed | 0.200 | simd | 0.349 | 1.747 |
| 100000 | splitmix | 99991 | adaptive_fixed | 0.206 | vq | 0.333 | 1.618 |
| 100000 | uniform | 1009 | adaptive_fixed | 0.205 | vq | 0.334 | 1.624 |
| 100000 | uniform | 12347 | adaptive_fixed | 0.198 | vq | 0.331 | 1.677 |
| 100000 | uniform | 99991 | adaptive_fixed | 0.196 | vq | 0.333 | 1.699 |
| 110000 | splitmix | 1009 | adaptive_fixed | 0.209 | vq | 0.368 | 1.757 |
| 110000 | splitmix | 12347 | adaptive_fixed | 0.213 | vq | 0.371 | 1.744 |
| 110000 | splitmix | 99991 | adaptive_fixed | 0.216 | vq | 0.374 | 1.728 |
| 110000 | uniform | 1009 | adaptive_fixed | 0.216 | vq | 0.368 | 1.704 |
| 110000 | uniform | 12347 | adaptive_fixed | 0.213 | vq | 0.373 | 1.747 |
| 110000 | uniform | 99991 | adaptive_fixed | 0.210 | vq | 0.369 | 1.754 |
| 130000 | splitmix | 1009 | adaptive_fixed | 0.327 | vq | 0.441 | 1.349 |
| 130000 | splitmix | 12347 | adaptive_fixed | 0.326 | simd | 0.459 | 1.405 |
| 130000 | splitmix | 99991 | adaptive_fixed | 0.328 | vq | 0.444 | 1.352 |
| 130000 | uniform | 1009 | adaptive_fixed | 0.328 | vq | 0.448 | 1.365 |
| 130000 | uniform | 12347 | adaptive_fixed | 0.328 | vq | 0.444 | 1.355 |
| 130000 | uniform | 99991 | adaptive_fixed | 0.329 | vq | 0.440 | 1.336 |
