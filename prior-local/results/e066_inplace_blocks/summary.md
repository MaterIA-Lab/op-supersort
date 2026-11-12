# E066 — Reparto in situ por bloques y finalización con vqsort

Medianas en ms. La puerta compara adaptive con vqsort completo en uniforme y prefijos amplios.

| Familia | Semilla | Fixed | Adaptive | Vqsort | Fixed / adaptive | Vqsort / adaptive | Margen a la meta (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 49.001132 | 56.349985 | 48.921856 | 0.869586 | 0.868179 | -17.212500 |
| uniform | 91009 | 51.333065 | 59.121546 | 51.518237 | 0.868263 | 0.871395 | -17.906956 |
| prefix_distinct | 42701 | 61.127721 | 54.427617 | 48.439619 | 1.123101 | 0.889982 | -15.675922 |
| prefix_distinct | 91009 | 66.690710 | 53.920960 | 51.871247 | 1.236823 | 0.961987 | -12.423962 |
| dominant | 42701 | 55.824409 | 56.652663 | 36.909712 | 0.985380 | 0.651509 | -27.124893 |
| dominant | 91009 | 57.834038 | 62.190651 | 41.513125 | 0.929947 | 0.667514 | -28.980151 |
| dense16 | 42701 | 44.586200 | 38.426253 | 36.697838 | 1.160306 | 0.955020 | -9.067983 |
| dense16 | 91009 | 49.786764 | 40.720621 | 39.785328 | 1.222643 | 0.977031 | -8.892359 |

## Fases y rangos

Las medianas de fases incluyen respaldos. La geometría resume solo las rondas de reparto por bloques.

| Familia | Semilla | Brazo | Elección y reparto (ms) | Finalización (ms) | Rangos | Tramo mayor | Rutas y rondas |
|---|---:|---|---:|---:|---:|---:|---|
| uniform | 42701 | fixed | 17.916912 | 30.722986 | 512 | 19994 | blocks 7 |
| uniform | 42701 | adaptive | 25.541348 | 30.652590 | 512 | 26609 | blocks 7 |
| uniform | 42701 | vq | 0.000000 | 48.921695 | — | — | vq 7 |
| uniform | 91009 | fixed | 18.074745 | 31.890055 | 512 | 19992 | blocks 7 |
| uniform | 91009 | adaptive | 26.859206 | 32.119725 | 512 | 26979 | blocks 7 |
| uniform | 91009 | vq | 0.000000 | 51.518027 | — | — | vq 7 |
| prefix_distinct | 42701 | fixed | 20.811473 | 40.289536 | 8 | 1250009 | blocks 7 |
| prefix_distinct | 42701 | adaptive | 23.093609 | 31.603836 | 512 | 39061 | blocks 7 |
| prefix_distinct | 42701 | vq | 0.000000 | 48.439449 | — | — | vq 7 |
| prefix_distinct | 91009 | fixed | 23.718090 | 42.157718 | 8 | 1250001 | blocks 7 |
| prefix_distinct | 91009 | adaptive | 22.928124 | 31.310012 | 512 | 29299 | blocks 7 |
| prefix_distinct | 91009 | vq | 0.000000 | 51.871067 | — | — | vq 7 |
| dominant | 42701 | fixed | 20.124083 | 35.620907 | 512 | 9499544 | blocks 7 |
| dominant | 42701 | adaptive | 21.582914 | 35.624012 | 27 | 9507784 | blocks 7 |
| dominant | 42701 | vq | 0.000000 | 36.909542 | — | — | vq 7 |
| dominant | 91009 | fixed | 20.939776 | 36.891558 | 512 | 9500695 | blocks 7 |
| dominant | 91009 | adaptive | 22.346720 | 38.557818 | 27 | 9507939 | blocks 7 |
| dominant | 91009 | vq | 0.000000 | 41.512955 | — | — | vq 7 |
| dense16 | 42701 | fixed | 7.192743 | 37.548707 | 1 | 10000000 | blocks 7 |
| dense16 | 42701 | adaptive | 0.754078 | 37.689208 | — | — | bypass 7 |
| dense16 | 42701 | vq | 0.000000 | 36.697678 | — | — | vq 7 |
| dense16 | 91009 | fixed | 8.473587 | 39.691967 | 1 | 10000000 | blocks 7 |
| dense16 | 91009 | adaptive | 0.783782 | 39.610028 | — | — | bypass 7 |
| dense16 | 91009 | vq | 0.000000 | 39.785127 | — | — | vq 7 |

Puerta fallida. Se cierra esta implementación.

- uniform/42701 alcanzó 0.868179 frente a vqsort, por debajo de 1.25.
- uniform/91009 alcanzó 0.871395 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.889982 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.961987 frente a vqsort, por debajo de 1.25.

168 muestras y 192 salidas exactas con calentamientos. 170 comprobaciones previas.
