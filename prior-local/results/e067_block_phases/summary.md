# E067 — Presupuesto por fase del reparto de E066

Medianas en ms. El resto se calcula por ronda como elección y reparto menos las tres fases medidas.

| Familia | Semilla | Brazo | Total | Reparto | Clasificación | Permutación | Márgenes | Resto | Finalización | Rangos | Tramo mayor | Rutas |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| uniform | 42701 | fixed | 47.770240 | 17.594745 | 9.927739 | 7.423022 | 0.030877 | 0.013496 | 30.388811 | 512 | 19994 | blocks 7 |
| uniform | 42701 | adaptive | 55.863255 | 25.418757 | 17.152079 | 6.944192 | 0.028833 | 0.720123 | 30.467499 | 512 | 26609 | blocks 7 |
| uniform | 42701 | vq | 49.496352 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 49.496202 | — | — | vq 7 |
| uniform | 91009 | fixed | 46.824015 | 16.333576 | 9.464836 | 7.109280 | 0.029896 | 0.012873 | 30.797342 | 512 | 19992 | blocks 7 |
| uniform | 91009 | adaptive | 55.837509 | 25.442086 | 17.236160 | 7.663604 | 0.027732 | 0.741514 | 30.459882 | 512 | 26979 | blocks 7 |
| uniform | 91009 | vq | 48.784634 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 48.784483 | — | — | vq 7 |
| prefix_distinct | 42701 | fixed | 59.941407 | 19.090611 | 14.877638 | 4.234553 | 0.002655 | 0.013836 | 40.732926 | 8 | 1250009 | blocks 7 |
| prefix_distinct | 42701 | adaptive | 54.368766 | 22.058610 | 14.150631 | 7.364617 | 0.027922 | 0.791207 | 32.073945 | 512 | 39061 | blocks 7 |
| prefix_distinct | 42701 | vq | 48.435081 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 48.434921 | — | — | vq 7 |
| prefix_distinct | 91009 | fixed | 62.382904 | 21.239392 | 16.698295 | 4.609048 | 0.002956 | 0.013164 | 40.796085 | 8 | 1250001 | blocks 7 |
| prefix_distinct | 91009 | adaptive | 51.668547 | 21.422934 | 13.317887 | 6.780336 | 0.026880 | 0.736055 | 30.234480 | 512 | 29299 | blocks 7 |
| prefix_distinct | 91009 | vq | 49.101214 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 49.101144 | — | — | vq 7 |

## Presupuesto al suprimir una fase

Tiempo hipotético como mediana de total menos fase por ronda. El margen resta ese tiempo al 80% de la mediana de vqsort de la misma tanda.

| Familia | Semilla | Brazo | Fase | Fase medida | Tiempo hipotético | Objetivo | Margen |
|---|---:|---|---|---:|---:|---:|---:|
| uniform | 42701 | fixed | Clasificación | 9.927739 | 37.842501 | 39.597082 | 1.754581 |
| uniform | 42701 | fixed | Permutación | 7.423022 | 40.335834 | 39.597082 | -0.738752 |
| uniform | 42701 | fixed | Márgenes | 0.030877 | 47.733100 | 39.597082 | -8.136018 |
| uniform | 42701 | fixed | Resto | 0.013496 | 47.756524 | 39.597082 | -8.159442 |
| uniform | 42701 | adaptive | Clasificación | 17.152079 | 38.908611 | 39.597082 | 0.688471 |
| uniform | 42701 | adaptive | Permutación | 6.944192 | 49.095874 | 39.597082 | -9.498792 |
| uniform | 42701 | adaptive | Márgenes | 0.028833 | 55.843548 | 39.597082 | -16.246466 |
| uniform | 42701 | adaptive | Resto | 0.720123 | 55.067746 | 39.597082 | -15.470664 |
| uniform | 91009 | fixed | Clasificación | 9.464836 | 37.604496 | 39.027707 | 1.423211 |
| uniform | 91009 | fixed | Permutación | 7.109280 | 40.540106 | 39.027707 | -1.512399 |
| uniform | 91009 | fixed | Márgenes | 0.029896 | 46.797366 | 39.027707 | -7.769659 |
| uniform | 91009 | fixed | Resto | 0.012873 | 46.811501 | 39.027707 | -7.783794 |
| uniform | 91009 | adaptive | Clasificación | 17.236160 | 38.486092 | 39.027707 | 0.541615 |
| uniform | 91009 | adaptive | Permutación | 7.663604 | 48.547876 | 39.027707 | -9.520169 |
| uniform | 91009 | adaptive | Márgenes | 0.027732 | 55.810589 | 39.027707 | -16.782882 |
| uniform | 91009 | adaptive | Resto | 0.741514 | 55.131001 | 39.027707 | -16.103294 |
| prefix_distinct | 42701 | fixed | Clasificación | 14.877638 | 44.907899 | 38.748065 | -6.159834 |
| prefix_distinct | 42701 | fixed | Permutación | 4.234553 | 55.476064 | 38.748065 | -16.727999 |
| prefix_distinct | 42701 | fixed | Márgenes | 0.002655 | 59.939103 | 38.748065 | -21.191038 |
| prefix_distinct | 42701 | fixed | Resto | 0.013836 | 59.928543 | 38.748065 | -21.180478 |
| prefix_distinct | 42701 | adaptive | Clasificación | 14.150631 | 40.472080 | 38.748065 | -1.724015 |
| prefix_distinct | 42701 | adaptive | Permutación | 7.364617 | 46.772609 | 38.748065 | -8.024544 |
| prefix_distinct | 42701 | adaptive | Márgenes | 0.027922 | 54.337908 | 38.748065 | -15.589843 |
| prefix_distinct | 42701 | adaptive | Resto | 0.791207 | 53.640508 | 38.748065 | -14.892443 |
| prefix_distinct | 91009 | fixed | Clasificación | 16.698295 | 45.480898 | 39.280971 | -6.199927 |
| prefix_distinct | 91009 | fixed | Permutación | 4.609048 | 57.329071 | 39.280971 | -18.048100 |
| prefix_distinct | 91009 | fixed | Márgenes | 0.002956 | 62.379948 | 39.280971 | -23.098977 |
| prefix_distinct | 91009 | fixed | Resto | 0.013164 | 62.371292 | 39.280971 | -23.090321 |
| prefix_distinct | 91009 | adaptive | Clasificación | 13.317887 | 37.755188 | 39.280971 | 1.525783 |
| prefix_distinct | 91009 | adaptive | Permutación | 6.780336 | 44.316184 | 39.280971 | -5.035213 |
| prefix_distinct | 91009 | adaptive | Márgenes | 0.026880 | 51.626669 | 39.280971 | -12.345698 |
| prefix_distinct | 91009 | adaptive | Resto | 0.736055 | 50.932492 | 39.280971 | -11.651521 |

## Comparación con E066

Medianas de tandas distintas. La diferencia da contexto sobre la instrumentación y la variación entre tandas.

| Familia | Semilla | Brazo | E066 | E067 | E067 − E066 | Diferencia relativa |
|---|---:|---|---:|---:|---:|---:|
| uniform | 42701 | fixed | 49.001132 | 47.770240 | -1.230892 | -2.51% |
| uniform | 42701 | adaptive | 56.349985 | 55.863255 | -0.486730 | -0.86% |
| uniform | 42701 | vq | 48.921856 | 49.496352 | 0.574496 | +1.17% |
| uniform | 91009 | fixed | 51.333065 | 46.824015 | -4.509050 | -8.78% |
| uniform | 91009 | adaptive | 59.121546 | 55.837509 | -3.284037 | -5.55% |
| uniform | 91009 | vq | 51.518237 | 48.784634 | -2.733603 | -5.31% |
| prefix_distinct | 42701 | fixed | 61.127721 | 59.941407 | -1.186314 | -1.94% |
| prefix_distinct | 42701 | adaptive | 54.427617 | 54.368766 | -0.058851 | -0.11% |
| prefix_distinct | 42701 | vq | 48.439619 | 48.435081 | -0.004538 | -0.01% |
| prefix_distinct | 91009 | fixed | 66.690710 | 62.382904 | -4.307806 | -6.46% |
| prefix_distinct | 91009 | adaptive | 53.920960 | 51.668547 | -2.252413 | -4.18% |
| prefix_distinct | 91009 | vq | 51.871247 | 49.101214 | -2.770033 | -5.34% |

Suprimir una sola fase deja al adaptativo fuera de la meta en alguna entrada.

84 muestras y 96 salidas exactas con calentamientos. 170 comprobaciones previas.
