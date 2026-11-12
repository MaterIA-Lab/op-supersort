# E045 — La tabla de tres sufijos pierde con el reparto preparado

2026-11-05. [[E045 - Prerregistro celdas]] y [[E045 - Adenda recuperación]]. Windows, Ryzen 7 5800X, GCC 16.1, CPU lógica 2. Hoja aislada con grupos por byte alto preparados fuera del tiempo. Cada llamada escribe el resultado en el destino final. El control copia el grupo y ejecuta vqsort en el destino.

| Familia, 10M | Celdas, mediana | Copia y vqsort, mediana | Observación de trabajo |
|---|---:|---:|---|
| Uniforme, 47143 | 94,78 ms | 37,18 ms | 256 grupos completados, 61.844 claves residuales |
| Uniforme, 92671 | 94,38 ms | 37,68 ms | 256 grupos completados, 62.086 claves residuales |
| Desbordamiento tardío, 47143 | 48,73 ms | 36,94 ms | 256 abortos en la última clave de cada grupo |
| Desbordamiento tardío, 92671 | 55,78 ms | 39,68 ms | 256 abortos en la última clave de cada grupo |

**Medido.** Los dos uniformes incumplen el filtro por separado. Los dos `late_overflow` pagan 10M lecturas de intento y todo el respaldo. En los casos completados de `dense16`, `bimodal`, `skew`, `prefix_distinct` y `few` se omitió la tabla en todos los grupos activos. Diferencias temporales en esas filas no son ahorro de ordenación por celdas. La prueba completa del sorter de celdas queda descartada por el filtro. [Matriz y fallos](../results/e045_cells_recovery/analysis-partial.md).

**Demostrado para la representación.** En un grupo admitido, cada aparición se conserva en una ranura o en el residual. El barrido ordena por dirección, y ordenar las ranuras y fusionar el residual conserva las multiplicidades. El respaldo recupera el grupo de la fuente original intacta y paga la ingestión ya hecha. Las guardas y 144 comparaciones previas cubrieron vacíos, límites de presupuesto, valores extremos, duplicados y reinicio de épocas. En los 15 casos completos, 210 muestras y 240 comparaciones exactas con los calentamientos. El argumento de la representación presupone que la llamada a la referencia termina correctamente. [Verificación y primer binario](../results/e045_cells_filter/verify.stdout.txt).

**Fallo abierto.** La primera entrada `dense16` terminó con una excepción de acceso de Windows. La reproducción del mismo binario con GDB terminó correctamente y se excluyó de la tabla. La recuperación única completó ambos `dense16` pero dejó sin completar un `skew` y los dos `mixed`, con el mismo código de excepción. En `dense16` ambos brazos ejecutan el mismo camino copia + vqsort. No se ha localizado la instrucción que falla ni establecido la causa. [Diagnóstico GDB](../results/e045_cells_filter/crash-gdb.txt), [estado de recuperación](../results/e045_cells_recovery/recovery-status.json).

**Hipótesis siguiente.** Un residuo de aproximadamente 0,62% coexistió con una pérdida de 2,5×. La medida agregada no distingue coste del barrido, dependencia de la tabla y reconstrucción. En cambio, la omisión por tamaño de ventanas densas es una limitación explícita del diseño. E046 cambia a multiplicidades completas para una o dos ventanas, con un certificado exacto y una ruta de rechazo de solo lectura. Su objetivo es ahorrar la ordenación de la masa densa y mantener el coste bajo cuando el rango efectivo es amplio. [[E046 - Prerregistro ventanas]].
