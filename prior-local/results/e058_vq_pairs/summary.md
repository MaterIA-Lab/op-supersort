# E058 — Presupuesto de pares de particiones de vqsort

Medianas en ms, salvo la calibración en ns y el número de pares. `Ideal` suma la menor duración de cada par. `≥1024` restringe esa suma a pares con ambos hijos de al menos 1.024 claves.

| Familia | Semilla | Vqsort | Traza | Partición total | Tiempo en pares | Ideal bruto | Ideal corregido | ≥1024 | Dos niveles superiores | Requerido | Reloj (ns) | Pares |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 46.020 | 51.012 | 34.590 | 31.332 | 13.781 | 12.752 | 10.010 | 5.466 | 9.204 | 20.0 | 51381 |
| uniform | 91009 | 46.232 | 51.338 | 34.788 | 31.457 | 13.873 | 12.845 | 10.145 | 5.262 | 9.246 | 20.0 | 51336 |
| prefix_distinct | 42701 | 45.739 | 50.517 | 34.299 | 31.098 | 13.459 | 12.431 | 9.716 | 5.372 | 9.148 | 20.0 | 51384 |
| prefix_distinct | 91009 | 45.712 | 50.376 | 34.068 | 30.654 | 13.414 | 12.386 | 9.694 | 5.030 | 9.142 | 20.0 | 51405 |

**Decisión: contrastar alternancia.**

Por debajo incluso en el modelo bruto: ninguna.
Margen incierto: ninguna.

56 tiempos completos y 64 salidas exactas con calentamientos. Los logs de cada brazo conservan la traza sin resumir.
