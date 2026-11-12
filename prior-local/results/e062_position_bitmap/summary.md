# E062 — Ordenar posiciones dentro de subárboles de vqsort

Tiempos en ms. Replay y bitmap repiten los mismos tramos capturados. El ahorro es la mediana de las diferencias por ronda. La meta usa el tiempo completo de vqsort.

| Familia | Semilla | Replay | Bitmap | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos bitmap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 18.006099 | 104.326354 | 45.894128 | -86.466630 | 9.178826 | 28457 | 10000000 | 28457 |
| uniform | 91009 | 18.783090 | 105.345555 | 46.043548 | -86.727145 | 9.208710 | 28461 | 10000000 | 28461 |
| prefix_distinct | 42701 | 18.306177 | 104.147722 | 47.723237 | -85.718873 | 9.544647 | 28455 | 10000000 | 28455 |
| prefix_distinct | 91009 | 18.251457 | 104.469702 | 45.704360 | -86.218245 | 9.140872 | 28442 | 10000000 | 28442 |

Puerta fallida. Se cierra esta implementación.

- uniform/42701 ahorró -86.466630 ms frente a 9.178826 ms requeridos.
- uniform/91009 ahorró -86.727145 ms frente a 9.208710 ms requeridos.
- prefix_distinct/42701 ahorró -85.718873 ms frente a 9.544647 ms requeridos.
- prefix_distinct/91009 ahorró -86.218245 ms frente a 9.140872 ms requeridos.

84 muestras, 96 salidas exactas de los brazos con calentamientos y 32 capturas verificadas. 4168 comprobaciones previas.
