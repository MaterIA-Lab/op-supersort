# E069 — Finalizador en la frontera de vqsort

Núcleo `include/supersort/frontier_radix24.hpp` y frontera de hasta 32768 claves por tramo.

Tiempos en ms. Replay y candidato reciben los mismos tramos capturados. El ahorro es la mediana de las diferencias por ronda y la meta usa el tiempo de vqsort completo.

| Familia | Semilla | Replay | Candidato | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos aceptados | Claves aceptadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 30.533854 | 28.730776 | 47.192929 | 1.719496 | 9.438586 | 446 | 10000000 | 446 | 10000000 |
| uniform | 91009 | 30.533031 | 28.606416 | 47.633921 | 1.875299 | 9.526784 | 444 | 10000000 | 444 | 10000000 |
| prefix_distinct | 42701 | 30.256015 | 39.924166 | 46.359113 | -9.767314 | 9.271823 | 446 | 10000000 | 443 | 9930722 |
| prefix_distinct | 91009 | 30.291235 | 40.656005 | 46.412085 | -10.171730 | 9.282417 | 448 | 10000000 | 445 | 9930871 |

Puerta fallida.

- uniform/42701 registró un ahorro de 1.719496 ms frente a los 9.438586 ms requeridos.
- uniform/91009 registró un ahorro de 1.875299 ms frente a los 9.526784 ms requeridos.
- prefix_distinct/42701 registró un ahorro de -9.767314 ms frente a los 9.271823 ms requeridos.
- prefix_distinct/91009 registró un ahorro de -10.171730 ms frente a los 9.282417 ms requeridos.

84 muestras, 96 salidas exactas de los brazos con calentamientos y 32 capturas verificadas. 4806 comprobaciones previas.
