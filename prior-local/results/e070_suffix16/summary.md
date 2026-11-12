# E070 — Finalizador en la frontera de vqsort

Núcleo `include/supersort/frontier_suffix16.hpp` y frontera de hasta 32768 claves por tramo.

Tiempos en ms. Replay y candidato reciben los mismos tramos capturados. El ahorro es la mediana de las diferencias por ronda y la meta usa el tiempo de vqsort completo.

| Familia | Semilla | Replay | Candidato | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos aceptados | Claves aceptadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 30.400921 | 34.705603 | 47.072259 | -4.270899 | 9.414452 | 446 | 10000000 | 446 | 10000000 |
| uniform | 91009 | 30.620321 | 34.674075 | 47.749313 | -4.090950 | 9.549863 | 444 | 10000000 | 444 | 10000000 |
| prefix_distinct | 42701 | 29.997659 | 82.489121 | 46.330864 | -52.638197 | 9.266173 | 446 | 10000000 | 443 | 9930722 |
| prefix_distinct | 91009 | 29.983350 | 81.366736 | 46.494995 | -51.297458 | 9.298999 | 448 | 10000000 | 445 | 9930871 |

Puerta fallida.

- uniform/42701 registró un ahorro de -4.270899 ms frente a los 9.414452 ms requeridos.
- uniform/91009 registró un ahorro de -4.090950 ms frente a los 9.549863 ms requeridos.
- prefix_distinct/42701 registró un ahorro de -52.638197 ms frente a los 9.266173 ms requeridos.
- prefix_distinct/91009 registró un ahorro de -51.297458 ms frente a los 9.298999 ms requeridos.

84 muestras, 96 salidas exactas de los brazos con calentamientos y 32 capturas verificadas. 4806 comprobaciones previas.
