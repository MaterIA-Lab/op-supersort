# E063 — Partición binaria por intercambio de posiciones

Medianas en ms. Los tiempos de partición suman los lotes medidos de cada ronda. El ahorro proyectado pondera la diferencia pareada de cada clase por población sobre muestra.

| Familia | Semilla | Partition | Exchange | Ahorro en muestra | Ahorro proyectado | Vqsort | Ahorro requerido |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 5.619066 | 15.128267 | -9.269935 | -83.996214 | 45.252790 | 9.050558 |
| uniform | 91009 | 5.735914 | 15.112241 | -9.376327 | -85.722845 | 45.983008 | 9.196602 |
| prefix_distinct | 42701 | 5.578246 | 13.111552 | -7.505690 | -78.336393 | 45.133172 | 9.026634 |
| prefix_distinct | 91009 | 5.455434 | 12.130094 | -6.793205 | -83.491924 | 45.189432 | 9.037886 |
| skew95 | 42701 | 3.246679 | 5.305690 | -2.061806 | -2.061806 | — | — |
| skew95 | 91009 | 3.023393 | 5.278181 | -2.352599 | -2.352599 | — | — |
| separated | 42701 | 3.099565 | 1.996125 | 0.999244 | 0.999244 | — | — |
| separated | 91009 | 3.043681 | 1.890799 | 1.232460 | 1.232460 | — | — |

## Cobertura y escrituras ponderadas

Se cuentan posiciones de 32 bits solicitadas al array. Partition incluye los stores anchos del bucle y de sus vectores guardados. Exchange incluye también los intercambios de cola. Las escrituras proyectadas usan los mismos pesos por clase que el tiempo.

| Familia | Semilla | Tramos por brazo | Claves muestreadas | Claves de población | Partition (M posiciones) | Exchange (M posiciones) |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 458 | 22631061 | 169350561 | 329.696 | 168.304 |
| uniform | 91009 | 458 | 22167438 | 169303469 | 329.765 | 168.268 |
| prefix_distinct | 42701 | 458 | 24386870 | 169287087 | 329.530 | 168.594 |
| prefix_distinct | 91009 | 458 | 23439237 | 169206232 | 329.330 | 167.436 |
| skew95 | 42701 | 1 | 10000000 | 10000000 | 20.000 | 3.704 |
| skew95 | 91009 | 1 | 10000000 | 10000000 | 20.000 | 3.698 |
| separated | 42701 | 1 | 10000000 | 10000000 | 20.000 | 0.000 |
| separated | 91009 | 1 | 10000000 | 10000000 | 20.000 | 0.000 |

Puerta fallida. Se cierra esta implementación.

- uniform/42701 proyectó -83.996214 ms frente a 9.050558 ms requeridos.
- uniform/91009 proyectó -85.722845 ms frente a 9.196602 ms requeridos.
- prefix_distinct/42701 proyectó -78.336393 ms frente a 9.026634 ms requeridos.
- prefix_distinct/91009 proyectó -83.491924 ms frente a 9.037886 ms requeridos.

1036 muestras, 29376 particiones verificadas y 32 salidas de vqsort con calentamientos. Además, 1836 particiones en la pasada de telemetría, 4 capturas exactas y 8224 comprobaciones previas.
