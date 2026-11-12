# E060 — Cuatro rangos en una pasada

Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.

| Familia | Semilla | Binario | Cuatro | Vqsort | Binario − cuatro (ms) | Binario / cuatro | Vqsort / cuatro |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 49.393813 | 92.795771 | 50.691052 | -43.401958 | 0.532285 | 0.546265 |
| uniform | 91009 | 47.211379 | 89.340725 | 46.998051 | -42.129346 | 0.528442 | 0.526054 |
| prefix_distinct | 42701 | 53.890108 | 64.204034 | 46.671315 | -10.313926 | 0.839357 | 0.726922 |
| prefix_distinct | 91009 | 55.582016 | 65.136735 | 47.230399 | -9.554719 | 0.853313 | 0.725096 |
| center | 42701 | 55.729964 | 97.439277 | 47.080469 | -41.709313 | 0.571946 | 0.483178 |
| center | 91009 | 53.364144 | 102.384615 | 49.848445 | -49.020471 | 0.521213 | 0.486874 |
| equal | 42701 | 9.327537 | 25.915442 | 2.011424 | -16.587905 | 0.359922 | 0.077615 |
| equal | 91009 | 10.110127 | 25.969624 | 1.960870 | -15.859497 | 0.389306 | 0.075506 |

## Trabajo lógico

Medianas en número de claves clasificadas y copiadas, y de tramos que activan el respaldo. El vqsort directo registra cero en los tres contadores. El ancho de los stores no se mide.

| Familia | Semilla | Binario clasificadas | Cuatro clasificadas | Cuatro copiadas | Binario respaldos | Cuatro respaldos |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 100000000 | 50000000 | 24998513 | 0 | 0 |
| uniform | 91009 | 100000000 | 50000000 | 24997371 | 0 | 0 |
| prefix_distinct | 42701 | 50000000 | 25000000 | 7500000 | 4 | 4 |
| prefix_distinct | 91009 | 50000000 | 25000000 | 7500000 | 4 | 4 |
| center | 42701 | 100000000 | 50000000 | 30000211 | 0 | 0 |
| center | 91009 | 100000000 | 50000000 | 29996926 | 0 | 0 |
| equal | 42701 | 20000000 | 10000000 | 10000000 | 1 | 1 |
| equal | 91009 | 20000000 | 10000000 | 10000000 | 1 | 1 |

Puerta del filtro fallida.

- uniform/42701 alcanzó 0.532285 frente al control binario, sin mejora.
- uniform/42701 alcanzó 0.546265 frente a vqsort, por debajo de 1.25.
- uniform/91009 alcanzó 0.528442 frente al control binario, sin mejora.
- uniform/91009 alcanzó 0.526054 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.839357 frente al control binario, sin mejora.
- prefix_distinct/42701 alcanzó 0.726922 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.853313 frente al control binario, sin mejora.
- prefix_distinct/91009 alcanzó 0.725096 frente a vqsort, por debajo de 1.25.

168 muestras y 192 salidas exactas con calentamientos. 4944 comprobaciones previas.
