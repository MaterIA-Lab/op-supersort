# E072 — Finalizador en la frontera de vqsort

Núcleo `include/supersort/frontier_radix8.hpp` y frontera de hasta 32768 claves por tramo.

Tiempos en ms. Replay y candidato reciben los mismos tramos capturados. El ahorro es la mediana de las diferencias por ronda y la meta usa el tiempo de vqsort completo.

| Familia | Semilla | Replay | Candidato | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos aceptados | Claves aceptadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 30.645776 | 124.660570 | 47.251675 | -92.441671 | 9.450335 | 446 | 10000000 | 446 | 10000000 |
| uniform | 91009 | 30.020700 | 126.268552 | 46.893033 | -95.858214 | 9.378607 | 444 | 10000000 | 444 | 10000000 |
| prefix_distinct | 42701 | 30.636909 | 118.585156 | 46.520758 | -87.101635 | 9.304152 | 446 | 10000000 | 443 | 9930722 |
| prefix_distinct | 91009 | 30.062080 | 117.711529 | 46.554112 | -87.934702 | 9.310822 | 448 | 10000000 | 445 | 9930871 |

Puerta fallida.

- uniform/42701 registró un ahorro de -92.441671 ms frente a los 9.450335 ms requeridos.
- uniform/91009 registró un ahorro de -95.858214 ms frente a los 9.378607 ms requeridos.
- prefix_distinct/42701 registró un ahorro de -87.101635 ms frente a los 9.304152 ms requeridos.
- prefix_distinct/91009 registró un ahorro de -87.934702 ms frente a los 9.310822 ms requeridos.

84 muestras, 96 salidas exactas de los brazos con calentamientos y 32 capturas verificadas. 4806 comprobaciones previas.
