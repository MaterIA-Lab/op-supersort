# E068 — Reparto por ciclos con límites preparados

Medianas en ms. Tabla y límites preparados en el brazo por ciclos. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.

| Familia | Semilla | Cycles | Blocks | Vqsort | Blocks / cycles | Vqsort / cycles | Margen a la meta (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 124.855562 | 54.624109 | 48.412089 | 0.437498 | 0.387745 | -86.125891 |
| uniform | 91009 | 133.069185 | 58.518907 | 51.066761 | 0.439763 | 0.383761 | -92.215776 |
| prefix_distinct | 42701 | 94.931095 | 53.968118 | 50.311733 | 0.568498 | 0.529982 | -54.681709 |
| prefix_distinct | 91009 | 93.380864 | 51.947646 | 52.347473 | 0.556299 | 0.560580 | -51.502886 |
| dominant | 42701 | 46.295716 | 57.109558 | 36.234377 | 1.233582 | 0.782672 | -17.308214 |
| dominant | 91009 | 44.653197 | 56.427515 | 37.126018 | 1.263684 | 0.831430 | -14.952383 |
| grouped | 42701 | 34.999682 | 43.396773 | 50.936720 | 1.239919 | 1.455348 | 5.749694 |
| grouped | 91009 | 34.938822 | 43.139114 | 51.419875 | 1.234704 | 1.471712 | 6.197078 |

## Fases y geometría

Las escrituras lógicas del reparto se cuentan fuera del reloj solo para cycles. Las medianas de fases incluyen respaldos y la geometría solo resume rondas repartidas.

| Familia | Semilla | Brazo | Reparto (ms) | Finalización (ms) | Rangos | Tramo mayor | Posiciones incorrectas | Escrituras | Rutas y rondas |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| uniform | 42701 | cycles | 95.240835 | 30.114930 | 512 | 26609 | 9980198 | 9980198 | cycles 7 |
| uniform | 42701 | blocks | 24.388795 | 29.991208 | 512 | 26609 | 9980198 | — | blocks 7 |
| uniform | 42701 | vq | 0.000000 | 48.411929 | — | — | 9980198 | — | vq 7 |
| uniform | 91009 | cycles | 100.712935 | 32.204568 | 512 | 26979 | 9980307 | 9980307 | cycles 7 |
| uniform | 91009 | blocks | 25.851164 | 31.178875 | 512 | 26979 | 9980307 | — | blocks 7 |
| uniform | 91009 | vq | 0.000000 | 51.066320 | — | — | 9980307 | — | vq 7 |
| prefix_distinct | 42701 | cycles | 62.764168 | 32.166777 | 512 | 39061 | 9979268 | 9979268 | cycles 7 |
| prefix_distinct | 42701 | blocks | 21.834381 | 32.817183 | 512 | 39061 | 9979268 | — | blocks 7 |
| prefix_distinct | 42701 | vq | 0.000000 | 50.311553 | — | — | 9979268 | — | vq 7 |
| prefix_distinct | 91009 | cycles | 62.731728 | 30.973824 | 512 | 29299 | 9979415 | 9979415 | cycles 7 |
| prefix_distinct | 91009 | blocks | 21.598668 | 30.302119 | 512 | 29299 | 9979415 | — | blocks 7 |
| prefix_distinct | 91009 | vq | 0.000000 | 52.347262 | — | — | 9979415 | — | vq 7 |
| dominant | 42701 | cycles | 9.458786 | 36.836799 | 27 | 9507784 | 959224 | 959224 | cycles 7 |
| dominant | 42701 | blocks | 20.782733 | 36.206987 | 27 | 9507784 | 959224 | — | blocks 7 |
| dominant | 42701 | vq | 0.000000 | 36.234207 | — | — | 959224 | — | vq 7 |
| dominant | 91009 | cycles | 9.537090 | 35.095599 | 27 | 9507939 | 959191 | 959191 | cycles 7 |
| dominant | 91009 | blocks | 20.394188 | 35.957937 | 27 | 9507939 | 959191 | — | blocks 7 |
| dominant | 91009 | vq | 0.000000 | 37.125957 | — | — | 959191 | — | vq 7 |
| grouped | 42701 | cycles | 4.641672 | 30.040652 | 512 | 26609 | 0 | 0 | cycles 7 |
| grouped | 42701 | blocks | 13.107827 | 30.491075 | 512 | 26609 | 0 | — | blocks 7 |
| grouped | 42701 | vq | 0.000000 | 50.936540 | — | — | 0 | — | vq 7 |
| grouped | 91009 | cycles | 4.783394 | 29.968408 | 512 | 26979 | 0 | 0 | cycles 7 |
| grouped | 91009 | blocks | 12.891166 | 30.276552 | 512 | 26979 | 0 | — | blocks 7 |
| grouped | 91009 | vq | 0.000000 | 51.419704 | — | — | 0 | — | vq 7 |

Puerta fallida. Se cierra el reparto por ciclos en este filtro preparado.

- uniform/42701 alcanzó 0.387745 frente a vqsort, por debajo de 1.25.
- uniform/42701 alcanzó 0.437498 frente a blocks, sin mejora.
- uniform/91009 alcanzó 0.383761 frente a vqsort, por debajo de 1.25.
- uniform/91009 alcanzó 0.439763 frente a blocks, sin mejora.
- prefix_distinct/42701 alcanzó 0.529982 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.568498 frente a blocks, sin mejora.
- prefix_distinct/91009 alcanzó 0.560580 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.556299 frente a blocks, sin mejora.

168 muestras y 192 salidas exactas con calentamientos. 7830 comprobaciones previas.
