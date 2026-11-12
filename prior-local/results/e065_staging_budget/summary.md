# E065 — Coste de materializar el reparto en un auxiliar nuevo

Medianas en ms. Staged cobra reserva, dos copias y liberación, además de los mismos finalizadores. La diferencia con oracle se calcula por pares y recoge también el contexto de caché.

| Familia | Semilla | Vqsort | Oracle | Staged | Staged − oracle pareado | Objetivo | Presupuesto | Respaldos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 46.929394 | 32.654515 | 62.293876 | 28.651652 | 37.543515 | -24.750361 | 0 |
| uniform | 91009 | 46.623116 | 32.936948 | 61.339505 | 28.282232 | 37.298493 | -24.041012 | 0 |
| prefix_distinct | 42701 | 46.257923 | 33.459585 | 61.821647 | 28.858533 | 37.006338 | -24.815309 | 0 |
| prefix_distinct | 91009 | 45.447433 | 32.597327 | 60.682108 | 28.199383 | 36.357946 | -24.324162 | 0 |

## Cobertura y tiempos de control

| Familia | Semilla | Tramos | Claves | Live total | Frontera en live | Replay |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 446 | 10000000 | 46.289149 | 28.611784 | 29.739953 |
| uniform | 91009 | 444 | 10000000 | 46.264136 | 28.743618 | 29.678007 |
| prefix_distinct | 42701 | 446 | 10000000 | 45.921417 | 28.618403 | 30.025169 |
| prefix_distinct | 91009 | 448 | 10000000 | 45.518544 | 28.435680 | 29.488838 |

Puerta fallida. Se cierra la secuencia de dos materializaciones separadas.

- uniform/42701 dejó -24.750361 ms para la clasificación y el directorio.
- uniform/91009 dejó -24.041012 ms para la clasificación y el directorio.
- prefix_distinct/42701 dejó -24.815309 ms para la clasificación y el directorio.
- prefix_distinct/91009 dejó -24.324162 ms para la clasificación y el directorio.

140 muestras, 160 salidas exactas de los brazos con calentamientos y 32 capturas exactas.
