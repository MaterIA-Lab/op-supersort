# E055 — Reparto por prefijo sin histograma global

Medianas en ms y cocientes frente al reparto con tramos virtuales. `dense16` es un control.

| Familia | Semilla | Contado | Virtual | Vqsort | Contado / virtual | Vqsort / virtual | Mayor cubeta |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 68.477164 | 65.396400 | 49.094171 | 1.047109 | 0.750717 | 39777 |
| uniform | 91009 | 71.063612 | 67.310520 | 52.381419 | 1.055758 | 0.778206 | 39660 |
| prefix_distinct | 42701 | 98.153054 | 90.912293 | 48.613741 | 1.079646 | 0.534732 | 2500000 |
| prefix_distinct | 91009 | 97.951941 | 92.179839 | 48.479943 | 1.062618 | 0.525928 | 2500000 |
| mixed | 42701 | 76.519471 | 69.254551 | 37.449933 | 1.104902 | 0.540758 | 5020879 |
| mixed | 91009 | 77.201566 | 75.458994 | 37.100204 | 1.023093 | 0.491660 | 5019371 |
| dense16 | 42701 | 76.882621 | 64.823128 | 36.845347 | 1.186037 | 0.568398 | 10000000 |
| dense16 | 91009 | 76.695151 | 66.285008 | 36.823316 | 1.157051 | 0.555530 | 10000000 |

Puerta del filtro fallida.

- uniform/42701 alcanzó 0.750717 frente a vqsort, por debajo de 1.25.
- uniform/42701 alcanzó 1.047109 frente al control, por debajo de 1.05.
- uniform/91009 alcanzó 0.778206 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.534732 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.525928 frente a vqsort, por debajo de 1.25.
- mixed/42701 alcanzó 0.540758 frente a vqsort, por debajo de 1.25.
- mixed/91009 alcanzó 0.491660 frente a vqsort, por debajo de 1.25.

168 muestras y 192 salidas exactas con calentamientos. 153 comprobaciones previas con guardas, incluido el fallo forzado de reserva.

