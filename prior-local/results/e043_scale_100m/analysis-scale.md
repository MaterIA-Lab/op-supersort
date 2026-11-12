# E043 — quick128 a escala

Ratio >1 favorece quick128. Las referencias son las de esta tanda. RSS máximo corresponde al proceso completo con todos los algoritmos. El CSV y summary.md conservan las mediciones de todos los algoritmos.

| n | distribución | semilla | quick128 mediana ms | quick128 min–max ms | DSO256/quick | host/quick | mejor referencia | mejor/quick | RSS pico MiB |
|---:|---|---:|---:|---:|---:|---:|---|---:|---:|
| 100000000 | few | 91573 | 167.699000 | 163.182000–169.417000 | 0.974 | 0.915 | simd | 0.915 | 1148.9 |
| 100000000 | forced_middle | 91573 | 673.369000 | 663.968000–731.163000 | 1.114 | 1.085 | vq | 0.999 | 1149.2 |
| 100000000 | uniform | 91573 | 604.556000 | 599.684000–619.579000 | 1.057 | 1.066 | vq | 0.960 | 1149.2 |

| n | entradas nominales | gana DSO256 | gana host | gana mejor referencia |
|---:|---:|---:|---:|---:|
| 100000000 | 3 | 2 | 2 | 0 |

63 muestras y 84 salidas exactas con calentamientos.
