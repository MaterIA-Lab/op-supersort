# Relevo para un sorter general

2026-11-05. El usuario aclara que la prioridad es ordenar claves aleatorias de cualquier tipo. El contrato sigue siendo CPU, un hilo, `uint32`, sin payload ni exigencia de estabilidad, con duplicados permitidos y salida en el array original. No se presupone uniformidad, independencia, rango estrecho ni orden inicial. Se exige exactitud para toda entrada válida y se busca una mejora práctica en familias diversas. Los tiempos de una matriz no demuestran superioridad para todas las entradas posibles.

## Qué llevar a la próxima sesión

- La reparación por certificados de [[19 - Rutas alternativas]] y [[21 - Decisión tras el análisis]] tiene una predicción sólida de escrituras para entradas casi ordenadas. Queda como especialización secundaria. El caso de veinte intercambios a 10M no representa aleatoriedad arbitraria.
- La tabla local de tres sufijos de [[20 - Diseño de celdas ordenadas]] es una pista para el objetivo general, todavía sin implementación ni tiempos. Las 62.149 claves residuales esperadas a 10M se deducen para claves uniformes independientes de todo el ancho. Los prefijos concentrados pueden generar un residual grande incluso con claves todas distintas. El fallback por grupo preserva la exactitud. Su coste, incluidas las operaciones ya realizadas antes de activarlo, forma parte del diseño.
- E007 ordenaba explícitamente casi solo duplicados y perdió frente a SIMD. Evitar comparaciones no basta. Hace falta justificar tráfico, localidad, coste de emisión y comportamiento adversario. E043 y E044 son la evidencia más reciente de escala y contadores. Quick128 es un ajuste conocido con mejoras y regresiones. [[15 - Escala y contadores]].
- Sufijos compactos, cubetas bufferizadas y agrupación por bloques tienen antecedentes cercanos. Separar qué elimina el mecanismo propuesto de qué reutiliza. No hay una aportación novedosa ni una victoria general verificadas. [[11 - Literatura y límites de novedad]], [[20 - Diseño de celdas ordenadas]].

## Qué criterio usar al avanzar

Comenzar por el coste completo y el adversario. Elegir un mecanismo que elimine trabajo en más de una familia o que mantenga un coste de rechazo medible cuando el mecanismo no sirve. Cualquier ruta adaptativa debe conservar exactitud aunque su diagnóstico se equivoque. Una muestra no certifica la distribución ni el orden del resto del array. Poner por escrito cuánto trabajo puede pagar un desvío tardío y qué evidencia obligaría a abandonar el diseño.

Si se retoma la tabla, el primer contraste causal usa el mismo reparto grueso con la hoja de celdas y con una hoja fuerte que ordena el tramo completo. Un diagnóstico con grupos preparados solo puede descartar costes, sin entrar en el ranking. Evaluar la variante completa solo si hay margen. Prerregistrar tamaños, semillas, referencias, adversarios, criterio de éxito y límites de regresión antes de medir. Comparar con vqsort, x86-simd-sort e IPS2Ra bajo el mismo contrato y conservar todas las pérdidas. Cobrar detección, reservas, copias, reconstrucción y fallback.

La matriz principal debe incluir claves uniformes de todo el ancho, rangos estrechos, distribuciones sesgadas y multimodales, muchas repeticiones y prefijos concentrados con sufijos distintos. Separar distribución de valores y orden de llegada. Dos intercalaciones de las mismas secuencias por prefijo permiten cambiar la localidad manteniendo fijo el trabajo dentro de cada grupo. Incluir ordenado y casi ordenado como controles, sin dejar que ese nicho determine qué se promueve. Objetivo inicial 10M, con tamaños menores para escala y límites a 100M documentados aparte. Exactitud contra `std::sort` fuera del tiempo en cada ejecución.

En esta actualización solo se guardó el relevo. E044 sigue siendo el último experimento. No se programó ningún candidato ni queda una ejecución pendiente.

Continuación experimental del 2026-11-05. [[23 - E045 celdas descartadas]] y [[24 - Ventanas y certificado]] contienen los resultados posteriores. El relevo actual se mantiene en [[04 - Reanudar]].
