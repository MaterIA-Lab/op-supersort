# E061 — Presupuesto de hojas de vqsort

Medianas por entrada. Los tiempos están en ms y el coste del reloj en ns. El presupuesto optimista de ocho aplica 7/8 al coste corregido de 65–128.

| Familia | Semilla | Vqsort | Traza | Hojas bruto | Hojas corregido | 65–128 corregido | Ideal ×8 | Requerido | Reloj (ns) | Claves en hojas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 46.862 | 45.998 | 11.513 | 9.244 | 8.612 | 7.536 | 9.372 | 20 | 10000000 |
| uniform | 91009 | 45.874 | 45.672 | 11.562 | 9.293 | 8.650 | 7.569 | 9.175 | 20 | 10000000 |
| prefix_distinct | 42701 | 45.341 | 45.042 | 11.448 | 9.178 | 8.550 | 7.481 | 9.068 | 20 | 10000000 |
| prefix_distinct | 91009 | 45.039 | 45.512 | 11.353 | 9.083 | 8.455 | 7.398 | 9.008 | 20 | 10000000 |

## Coste por franja

| Familia | Semilla | Tamaños | Hojas | Cronometradas | Bruto (ms) | Corregido (ms) | Rondas con hojas sin observación |
|---|---:|---|---:|---:|---:|---:|---:|
| uniform | 42701 | 1–16 | 0 | 0 | 0.000 | 0.000 | 0 |
| uniform | 42701 | 17–32 | 5 | 0 | 0.000 | 0.000 | 6 |
| uniform | 42701 | 33–64 | 11400 | 712 | 0.859 | 0.630 | 0 |
| uniform | 42701 | 65–128 | 102120 | 6374 | 10.655 | 8.612 | 0 |
| uniform | 91009 | 1–16 | 0 | 0 | 0.000 | 0.000 | 0 |
| uniform | 91009 | 17–32 | 6 | 0 | 0.000 | 0.000 | 4 |
| uniform | 91009 | 33–64 | 11311 | 700 | 0.849 | 0.621 | 0 |
| uniform | 91009 | 65–128 | 102144 | 6420 | 10.694 | 8.650 | 0 |
| prefix_distinct | 42701 | 1–16 | 0 | 0 | 0.000 | 0.000 | 0 |
| prefix_distinct | 42701 | 17–32 | 8 | 0 | 0.000 | 0.000 | 6 |
| prefix_distinct | 42701 | 33–64 | 11321 | 712 | 0.849 | 0.624 | 0 |
| prefix_distinct | 42701 | 65–128 | 102116 | 6378 | 10.593 | 8.550 | 0 |
| prefix_distinct | 91009 | 1–16 | 0 | 0 | 0.000 | 0.000 | 1 |
| prefix_distinct | 91009 | 17–32 | 7 | 0 | 0.000 | 0.000 | 6 |
| prefix_distinct | 91009 | 33–64 | 11295 | 718 | 0.855 | 0.628 | 0 |
| prefix_distinct | 91009 | 65–128 | 102187 | 6497 | 10.498 | 8.455 | 0 |

**Decisión: descartar.**

Por debajo en el modelo de ocho: uniform/42701, uniform/91009, prefix_distinct/42701, prefix_distinct/91009.
Margen incierto: ninguna.

56 tiempos completos y 112 salidas exactas con calentamientos.
