# E034 — análisis cerrado por distribución

Candidato principal preregistrado: adaptive_e034. Referencia = menor mediana entre las referencias externas de la misma entrada. Control adaptive_fixed y secundario predictk1280 nunca entran en ese mínimo. Ratios >1 favorecen al candidato. Sin selección retrospectiva.

| distribución | entradas | principal gana | ratio mínimo | ratio máximo |
|---|---:|---:|---:|---:|
| dense16 | 12 | 5 | 0.985 | 1.025 |
| equal | 12 | 0 | 0.899 | 0.988 |
| few | 12 | 4 | 0.928 | 1.021 |
| near_sorted | 12 | 0 | 0.510 | 0.932 |
| prefixcluster | 12 | 3 | 0.915 | 1.014 |
| reverse | 12 | 0 | 0.092 | 0.996 |
| samplemiss | 12 | 0 | 0.784 | 0.999 |
| sampletrap | 12 | 8 | 0.854 | 1.315 |
| skew | 12 | 3 | 0.923 | 1.015 |
| sorted | 12 | 4 | 0.086 | 1.868 |
| splitmix | 12 | 12 | 1.046 | 1.319 |
| uniform | 12 | 10 | 0.921 | 1.351 |

Nicho principal dentro de rango: 19/20; rango 0.921–1.351.

Entradas de nicho que no cumplen >1:
(0.9208917698366359, 68000, 'uniform', 2027)

Secundario fijo K1280 en 129000: [(1.3321584353027536, 129000, 'uniform', 2027), (1.1054780639753805, 129000, 'uniform', 7907), (1.3070048953627453, 129000, 'splitmix', 2027), (1.18508281491981, 129000, 'splitmix', 7907)]

Peor caso principal: (0.08626669879496765, 131073, 'sorted', 7907)
