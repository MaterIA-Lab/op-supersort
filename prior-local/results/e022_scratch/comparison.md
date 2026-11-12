# Comparación por entrada

Cada fila resume las medianas de las repeticiones de una entrada. Elegir retrospectivamente el mejor local es optimista: aún no es un selector desplegable.

| n | distribución | semilla | candidato | ms | mejor referencia | ms | referencia / candidato |
|---:|---|---:|---|---:|---|---:|---:|
| 1000000 | splitmix | 271 | local8nt | 5.093 | vq | 4.029 | 0.791 |
| 1000000 | splitmix | 811 | local8ntscratch | 4.695 | vq | 3.986 | 0.849 |
| 1000000 | splitmix | 1601 | local8ntscratch | 4.820 | vq | 4.027 | 0.835 |
| 1000000 | uniform | 271 | local10ntscratch | 5.436 | vq | 4.022 | 0.740 |
| 1000000 | uniform | 811 | local8ntscratch | 4.808 | vq | 4.092 | 0.851 |
| 1000000 | uniform | 1601 | local8ntscratch | 4.823 | vq | 4.024 | 0.834 |
| 10000000 | splitmix | 271 | local10nt | 51.484 | vq | 49.557 | 0.963 |
| 10000000 | splitmix | 811 | local10nt | 51.523 | vq | 49.976 | 0.970 |
| 10000000 | splitmix | 1601 | two8x9nt | 51.203 | vq | 50.107 | 0.979 |
| 10000000 | uniform | 271 | local10nt | 50.845 | vq | 48.342 | 0.951 |
| 10000000 | uniform | 811 | local10nt | 50.751 | vq | 48.038 | 0.947 |
| 10000000 | uniform | 1601 | two8x9nt | 48.069 | vq | 50.748 | 1.056 |
