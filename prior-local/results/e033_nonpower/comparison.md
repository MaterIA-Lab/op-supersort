# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 70000 | splitmix | 1009 | predictk1280 | 0.165 | vq | 0.221 | 1.341 |
| 70000 | splitmix | 12347 | predictk1280 | 0.164 | vq | 0.222 | 1.353 |
| 70000 | splitmix | 99991 | predictk768 | 0.165 | vq | 0.220 | 1.330 |
| 70000 | uniform | 1009 | predictk1280 | 0.165 | vq | 0.224 | 1.356 |
| 70000 | uniform | 12347 | predictk1280 | 0.165 | vq | 0.224 | 1.356 |
| 70000 | uniform | 99991 | predictk1280 | 0.164 | vq | 0.222 | 1.353 |
| 100000 | splitmix | 1009 | predict_fixed | 0.236 | vq | 0.326 | 1.379 |
| 100000 | splitmix | 12347 | predict_fixed | 0.236 | vq | 0.325 | 1.376 |
| 100000 | splitmix | 99991 | predict_fixed | 0.234 | vq | 0.323 | 1.380 |
| 100000 | uniform | 1009 | predict_fixed | 0.236 | vq | 0.324 | 1.370 |
| 100000 | uniform | 12347 | predict_fixed | 0.235 | vq | 0.326 | 1.387 |
| 100000 | uniform | 99991 | predict_fixed | 0.237 | vq | 0.327 | 1.380 |
| 130000 | splitmix | 1009 | predictk1280 | 0.319 | vq | 0.425 | 1.332 |
| 130000 | splitmix | 12347 | predictk1280 | 0.307 | vq | 0.427 | 1.391 |
| 130000 | splitmix | 99991 | predictk1280 | 0.311 | vq | 0.433 | 1.393 |
| 130000 | uniform | 1009 | predictk1280 | 0.308 | vq | 0.427 | 1.385 |
| 130000 | uniform | 12347 | predictk1280 | 0.308 | vq | 0.426 | 1.383 |
| 130000 | uniform | 99991 | predictk1280 | 0.309 | vq | 0.424 | 1.371 |
| 1000000 | splitmix | 1009 | predict13raw | 3.938 | vq | 3.764 | 0.956 |
| 1000000 | splitmix | 12347 | predictk768 | 3.926 | vq | 3.734 | 0.951 |
| 1000000 | splitmix | 99991 | predictk768 | 4.074 | vq | 3.745 | 0.919 |
| 1000000 | uniform | 1009 | predict13raw | 3.791 | vq | 3.728 | 0.983 |
| 1000000 | uniform | 12347 | predict13raw | 3.836 | vq | 3.788 | 0.988 |
| 1000000 | uniform | 99991 | predict13raw | 3.625 | vq | 3.773 | 1.041 |
