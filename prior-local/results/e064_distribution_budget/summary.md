# E064 — Presupuesto de un reparto grueso antes de vqsort

Medianas en ms. Oracle cobra una copia secuencial de la disposición preparada y los finalizadores. El presupuesto resta ese tiempo al 80% de vqsort completo.

| Familia | Semilla | Vqsort | Live total | Frontera en live | Replay | Oracle | Objetivo | Presupuesto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 45.796097 | 45.695801 | 28.528209 | 29.823339 | 32.774826 | 36.636878 | 3.862052 |
| uniform | 91009 | 45.760434 | 46.335229 | 28.203263 | 29.295204 | 32.519620 | 36.608347 | 4.088727 |
| prefix_distinct | 42701 | 46.020260 | 46.567972 | 28.142629 | 29.669653 | 32.575495 | 36.816208 | 4.240713 |
| prefix_distinct | 91009 | 46.076903 | 46.524539 | 28.736904 | 29.564714 | 33.249409 | 36.861522 | 3.612113 |

## Cobertura y diferencias por ronda

Las diferencias son medianas de pares. La diferencia entre oracle y replay incluye los efectos de caché de hacer la copia dentro del reloj.

| Familia | Semilla | Tramos | Claves | Live total − frontera | Replay − frontera | Oracle − replay |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 446 | 10000000 | 17.176165 | 0.930102 | 3.178992 |
| uniform | 91009 | 444 | 10000000 | 18.181735 | 1.038180 | 3.304386 |
| prefix_distinct | 42701 | 446 | 10000000 | 18.087328 | 1.440395 | 2.931341 |
| prefix_distinct | 91009 | 448 | 10000000 | 17.994344 | 0.607527 | 3.684695 |

Quedan al menos 3.612113 ms para detección, reserva y reparto reales.


112 muestras, 128 salidas exactas de los brazos con calentamientos y 32 capturas exactas.
