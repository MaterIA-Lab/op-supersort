# Interpretación E037

Principal fijo merge_natural. No se sustituyó por controles ni se eligió variante por entrada.

Criterio de mecanismo falla: dos pérdidas leves runs4096. Umbral de sobrecoste10% en uniform/splitmix pasa, aunque suele haber pérdida pequeña. Run_heavy pierde8/8 por21.7–38.9%. Principal gana a mejor referencia solo3/152 nominales, todos sorted, por1.3–6.1%; no victoria robusta de familia ni sorter competitivo general.

En73001/run_heavy/4243, fixed mezcla306637 elementos y escribe730010 por nivel; natural mezcla578023 y escribe584008. Menos escrituras pero más mezcla real, compatible con perder tiempo. En73001/runs4096/4243, merged_elements342610 para ambos; se ahorran niveles de copia y hojas, sin reducir el trabajo de mezcla superior. No inferir ciclos exactos ni DRAM de estas cuentas.

152 casos nominales son como máximo140 datasets distintos: equal/alternating/plateaus ignoran semilla. Dos comprobaciones instrumentadas adicionales por caso, fuera del índice de tiempos completos. Dispersión y todos los negativos están en analysis-runs.md y raw.csv.

Siguiente propuesta: política del árbol ponderada con mismo ejecutor en ambos controles, nueva matriz y prerregistro. E038 no ejecutada. El mecanismo ya tiene antecedentes en Powersort; no reclamar novedad ni mejora garantizada.
