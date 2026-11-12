# E045 — Recuperación parcial

La matriz quedó incompleta. El filtro prerregistrado requiere todas las entradas.

| Familia | Semilla | vqsort local, ms | Celdas, ms | vq/celdas |
|---|---:|---:|---:|---:|
| uniform | 47143 | 37.181000 | 94.778400 | 0.392294 |
| uniform | 92671 | 37.680500 | 94.382200 | 0.399233 |
| dense16 | 47143 | 41.243200 | 40.260500 | 1.024409 |
| dense16 | 92671 | 40.146200 | 40.046700 | 1.002485 |
| skew | 47143 | — | — | — |
| skew | 92671 | 29.377300 | 29.323600 | 1.001831 |
| bimodal | 47143 | 27.992200 | 27.142700 | 1.031298 |
| bimodal | 92671 | 27.317200 | 27.770700 | 0.983670 |
| mixed | 47143 | — | — | — |
| mixed | 92671 | — | — | — |
| prefix_distinct | 47143 | 47.599200 | 47.774800 | 0.996324 |
| prefix_distinct | 92671 | 48.492200 | 49.376900 | 0.982083 |
| few | 47143 | 5.254600 | 5.028300 | 1.045005 |
| few | 92671 | 6.074000 | 5.084000 | 1.194729 |
| late_overflow | 47143 | 36.937800 | 48.726200 | 0.758069 |
| late_overflow | 92671 | 39.681400 | 55.783600 | 0.711345 |
| near_sorted | 47143 | 39.121600 | 94.236000 | 0.415145 |
| near_sorted | 92671 | 38.365400 | 90.653400 | 0.423210 |

15 de 18 entradas completas. 210 muestras y 240 salidas exactas con calentamientos en las entradas completas.

- skew/47143 falló. case-skew-47143 exited with 3221225477. See A:\Users\elseb\Terminal\AI\Codex\supersort\results\e045_cells_recovery\case-skew-47143.stderr.txt.
- mixed/47143 falló. case-mixed-47143 exited with 3221225477. See A:\Users\elseb\Terminal\AI\Codex\supersort\results\e045_cells_recovery\case-mixed-47143.stderr.txt.
- mixed/92671 falló. case-mixed-92671 exited with 3221225477. See A:\Users\elseb\Terminal\AI\Codex\supersort\results\e045_cells_recovery\case-mixed-92671.stderr.txt.
