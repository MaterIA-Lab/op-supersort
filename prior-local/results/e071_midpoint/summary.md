# E071 — Finalizador en la frontera de vqsort

Núcleo `include/supersort/frontier_midpoint.hpp` y frontera de hasta 32768 claves por tramo.

Tiempos en ms. Replay y candidato reciben los mismos tramos capturados. El ahorro es la mediana de las diferencias por ronda y la meta usa el tiempo de vqsort completo.

| Familia | Semilla | Replay | Candidato | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos aceptados | Claves aceptadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 30.239526 | 25.859788 | 47.182156 | 4.380076 | 9.436431 | 446 | 10000000 | 446 | 10000000 |
| uniform | 91009 | 30.678328 | 26.193127 | 47.365307 | 4.487665 | 9.473061 | 444 | 10000000 | 444 | 10000000 |
| prefix_distinct | 42701 | 30.568043 | 25.433858 | 46.864563 | 5.131980 | 9.372913 | 446 | 10000000 | 446 | 10000000 |
| prefix_distinct | 91009 | 30.152828 | 25.182933 | 46.935843 | 5.016462 | 9.387169 | 448 | 10000000 | 448 | 10000000 |

Puerta fallida.

- uniform/42701 registró un ahorro de 4.380076 ms frente a los 9.436431 ms requeridos.
- uniform/91009 registró un ahorro de 4.487665 ms frente a los 9.473061 ms requeridos.
- prefix_distinct/42701 registró un ahorro de 5.131980 ms frente a los 9.372913 ms requeridos.
- prefix_distinct/91009 registró un ahorro de 5.016462 ms frente a los 9.387169 ms requeridos.

84 muestras, 96 salidas exactas de los brazos con calentamientos y 32 capturas verificadas. 4806 comprobaciones previas.
