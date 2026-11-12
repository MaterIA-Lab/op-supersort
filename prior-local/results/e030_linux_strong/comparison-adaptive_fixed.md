# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Candidato fijo: adaptive_fixed

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 65536 | splitmix | 17 | adaptive_fixed | 0.166 | vq | 0.207 | 1.247 |
| 65536 | splitmix | 83 | adaptive_fixed | 0.166 | vq | 0.208 | 1.257 |
| 65536 | splitmix | 501 | adaptive_fixed | 0.167 | vq | 0.212 | 1.268 |
| 65536 | uniform | 17 | adaptive_fixed | 0.176 | vq | 0.211 | 1.199 |
| 65536 | uniform | 83 | adaptive_fixed | 0.169 | vq | 0.207 | 1.225 |
| 65536 | uniform | 501 | adaptive_fixed | 0.174 | vq | 0.206 | 1.186 |
| 100000 | splitmix | 17 | adaptive_fixed | 0.265 | vq | 0.326 | 1.233 |
| 100000 | splitmix | 83 | adaptive_fixed | 0.253 | vq | 0.325 | 1.285 |
| 100000 | splitmix | 501 | adaptive_fixed | 0.253 | vq | 0.327 | 1.291 |
| 100000 | uniform | 17 | adaptive_fixed | 0.248 | vq | 0.327 | 1.317 |
| 100000 | uniform | 83 | adaptive_fixed | 0.250 | vq | 0.330 | 1.323 |
| 100000 | uniform | 501 | adaptive_fixed | 0.260 | vq | 0.333 | 1.282 |
| 131072 | splitmix | 17 | adaptive_fixed | 0.491 | vq | 0.443 | 0.901 |
| 131072 | splitmix | 83 | adaptive_fixed | 0.460 | vq | 0.444 | 0.966 |
| 131072 | splitmix | 501 | adaptive_fixed | 0.450 | vq | 0.444 | 0.985 |
| 131072 | uniform | 17 | adaptive_fixed | 0.415 | vq | 0.438 | 1.054 |
| 131072 | uniform | 83 | adaptive_fixed | 0.415 | vq | 0.441 | 1.064 |
| 131072 | uniform | 501 | adaptive_fixed | 0.469 | vq | 0.444 | 0.947 |
| 1000000 | splitmix | 17 | adaptive_fixed | 3.908 | vq | 3.866 | 0.989 |
| 1000000 | splitmix | 83 | adaptive_fixed | 3.826 | vq | 3.811 | 0.996 |
| 1000000 | splitmix | 501 | adaptive_fixed | 3.788 | vq | 3.757 | 0.992 |
| 1000000 | uniform | 17 | adaptive_fixed | 3.812 | vq | 3.821 | 1.002 |
| 1000000 | uniform | 83 | adaptive_fixed | 3.763 | vq | 3.746 | 0.996 |
| 1000000 | uniform | 501 | adaptive_fixed | 3.766 | vq | 3.789 | 1.006 |
| 10000000 | splitmix | 17 | adaptive_fixed | 44.951 | vq | 45.531 | 1.013 |
| 10000000 | splitmix | 83 | adaptive_fixed | 46.199 | vq | 46.677 | 1.010 |
| 10000000 | splitmix | 501 | adaptive_fixed | 46.094 | vq | 45.888 | 0.996 |
| 10000000 | uniform | 17 | adaptive_fixed | 45.695 | vq | 46.140 | 1.010 |
| 10000000 | uniform | 83 | adaptive_fixed | 46.907 | vq | 46.753 | 0.997 |
| 10000000 | uniform | 501 | adaptive_fixed | 45.996 | vq | 45.821 | 0.996 |
