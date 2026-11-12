# E034 — análisis cerrado por distribución

Candidato principal preregistrado: adaptive_e034. Referencia = menor mediana entre las referencias externas de la misma entrada. Control adaptive_fixed y secundario predictk1280 nunca entran en ese mínimo. Ratios >1 favorecen al candidato. Sin selección retrospectiva.

| distribución | entradas | principal gana | ratio mínimo | ratio máximo |
|---|---:|---:|---:|---:|
| dense16 | 12 | 5 | 0.958 | 1.011 |
| equal | 12 | 0 | 0.896 | 1.000 |
| few | 12 | 7 | 0.954 | 1.035 |
| near_sorted | 12 | 0 | 0.481 | 0.938 |
| prefixcluster | 12 | 6 | 0.987 | 1.008 |
| reverse | 12 | 10 | 0.367 | 4.343 |
| samplemiss | 12 | 0 | 0.928 | 0.997 |
| sampletrap | 12 | 10 | 0.614 | 1.718 |
| skew | 12 | 4 | 0.969 | 1.004 |
| sorted | 12 | 1 | 0.150 | 1.203 |
| splitmix | 12 | 10 | 0.992 | 1.718 |
| uniform | 12 | 11 | 0.994 | 1.709 |

Nicho principal dentro de rango: 19/20; rango 0.994–1.718.

Entradas de nicho que no cumplen >1:
(0.9941089837997056, 114689, 'splitmix', 7907)

Secundario fijo K1280 en 129000: [(1.5743571924947881, 129000, 'uniform', 2027), (1.6785714285714286, 129000, 'uniform', 7907), (1.6940436551979283, 129000, 'splitmix', 2027), (1.6276747503566333, 129000, 'splitmix', 7907)]

Peor caso principal: (0.14980824544582932, 131073, 'sorted', 2027)
