# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 100000 | splitmix | 271 | predict10s4 | 0.291 | vq | 0.344 | 1.184 |
| 100000 | splitmix | 811 | predict10s4 | 0.290 | vq | 0.345 | 1.187 |
| 100000 | splitmix | 1601 | predict10s4 | 0.243 | vq | 0.344 | 1.415 |
| 100000 | uniform | 271 | predict10s4 | 0.259 | vq | 0.341 | 1.317 |
| 100000 | uniform | 811 | predict10s4 | 0.321 | vq | 0.347 | 1.083 |
| 100000 | uniform | 1601 | predict10s4 | 0.244 | vq | 0.343 | 1.402 |
| 1000000 | splitmix | 271 | local8nt | 4.886 | vq | 3.941 | 0.807 |
| 1000000 | splitmix | 811 | local8nt | 4.793 | vq | 3.947 | 0.823 |
| 1000000 | splitmix | 1601 | local8nt | 4.709 | vq | 3.934 | 0.835 |
| 1000000 | uniform | 271 | local10nt | 5.453 | vq | 3.952 | 0.725 |
| 1000000 | uniform | 811 | local10nt | 5.429 | vq | 3.948 | 0.727 |
| 1000000 | uniform | 1601 | local8nt | 4.768 | vq | 3.958 | 0.830 |
| 10000000 | splitmix | 271 | two8x9nt | 49.441 | vq | 49.761 | 1.006 |
| 10000000 | splitmix | 811 | two8x9nt | 51.405 | vq | 49.914 | 0.971 |
| 10000000 | splitmix | 1601 | two8x9nt | 50.931 | vq | 49.853 | 0.979 |
| 10000000 | uniform | 271 | two9x8nt | 49.906 | vq | 49.841 | 0.999 |
| 10000000 | uniform | 811 | two8x9nt | 50.953 | vq | 48.867 | 0.959 |
| 10000000 | uniform | 1601 | two8x9nt | 47.275 | vq | 49.307 | 1.043 |
