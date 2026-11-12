# Reanudar SuperSort

## Último relevo experimental

2026-11-06. E054 sigue como candidato compuesto. Meta operativa 1,25× ante la mejor referencia externa por caso principal de 10M, con todos los costes y un hilo. Pasa 10/22 ante vqsort, x86-simd-sort e IPS2Ra, ambas semillas de few, few_permute, dense16, skew y bimodal. Quedan uniforme, prefijos amplios, mezcla 50/50, equal, few_powers y few_dominant. [Matriz y pérdidas](../results/e054_combined_full/summary.md).

E055 demuestra el invariante de longitud por cursor, incluida la cola parcial. Quitó el histograma inicial con tramos virtuales por byte alto. El primer intento falló la verificación por el cursor de cola y quedó archivado sin tiempos. En la recuperación, 153 comprobaciones previas, 168 muestras y 192 salidas exactas. La variante mejora la mediana frente al control en 2,3–18,6% como razón de velocidad, pero da 0,751–0,778× frente a vqsort en uniforme, 0,526–0,535× en prefijos amplios y 0,492–0,541× en mezcla. Falla la puerta y queda descartada sin ampliación. El ahorro observado incluye el cambio de reserva y de disposición de páginas. [[E055 - Prerregistro cubetas virtuales]]. [Matriz](../results/e055_virtual_filter_recovery/summary.md).

E056 hace dos particiones binarias SIMD in situ en los límites de una ventana propuesta. El corte alto acota el prefijo del corte bajo. El centro contiene exactamente los internos, incluso si la muestra sobrestima su presencia. Pasa el filtro inicial en las dos `mixed` con 1,251× y 1,261× frente a vqsort. La confirmación de tres referencias y cuatro semillas gana a E049 en todas por 1,180–1,275× y a vqsort, la mejor externa, por 1,196×, 1,275×, 1,228× y 1,239×. Solo pasa 91009. Falta hasta 1,375 ms para la meta en esa tanda. Pierde frente a E049 en `dense16` y frente a vqsort en `late_miss`. Uniforme y prefijos amplios delegan. Las dos tandas suman 630 muestras y 720 salidas exactas con calentamientos. La puerta de confirmación aplaza la integración. [Filtro](../results/e056_binary_filter/summary.md), [confirmación](../results/e056_binary_full/summary.md).

E057 prueba la primera idea general de la nueva tanda. Encadena dos niveles de unión AVX2 con dos bloques reutilizables de 2.048 claves, frente al mismo árbol con intermedios completos. Reduce su reserva intermedia de 40 MB a 16 KiB y gana 1,170–1,210× al control en los ocho casos. En uniforme da 0,517–0,526× frente a vqsort y en prefijos amplios 0,551×. Falla la puerta y no se amplía. 1.320 comprobaciones previas, 168 muestras y 192 salidas exactas. Origami queda como antecedente pendiente de una adaptación para medirlo directamente. [[E057 - Prerregistro unión en caché]]. [Matriz](../results/e057_stream_merge/summary.md).

E058 midió 30,65–31,46 ms en pares de particiones hermanas de vqsort con traza, en uniforme y prefijos amplios. Solapar por completo la llamada corta de cada par daría 13,41–13,87 ms brutos y 12,39–12,85 ms con la corrección del reloj. Vqsort limpio dio 45,71–46,23 ms y exige ahorrar 9,14–9,25 ms. La traza añade 4,66–5,11 ms al total. Pasan las cuatro entradas para medir la alternancia real. 56 tiempos completos y 64 salidas exactas contando la primera ronda descartada. [[E058 - Prerregistro pares de vqsort]]. [Matriz y trazas](../results/e058_vq_pairs/summary.md).

E059 alterna un bloque de cuatro vectores de cada tramo hermano, frente a terminar uno antes de empezar el otro. Los brazos conservan los mismos cortes y movimientos. Gana 2,44–3,20 ms frente a su control en uniforme y prefijos amplios, 26/28 rondas. Frente a vqsort directo queda en 0,971–1,004× y faltan 9,19–10,69 ms para la meta. Pierde en tres de cuatro medianas prioritarias y en ambas `equal` frente a su control. El filtro se cierra sin ampliación. 126 muestras, 144 salidas exactas con calentamientos y 1.590 comprobaciones previas. Los dos brazos propios preparan el hijo derecho antes de descender por la izquierda, con un árbol potencialmente distinto del de vqsort directo. [[E059 - Prerregistro alternancia de bloques]]. [Matriz y muestras](../results/e059_pair_schedule/summary.md).

E060 clasifica por dos bits en una pasada frente a dos niveles binarios con los mismos cortes. Repite hasta seis dígitos con hojas vqsort. Coloca los rangos externos in situ y copia los centrales desde un auxiliar de `n + 16` claves. En uniforme clasifica 50M claves acumuladas frente a 100M y copia 25M al hueco. Tarda 89,34–92,80 ms frente a 47,21–49,39 ms del control y 47,00–50,69 ms de vqsort. También pierde frente al control en prefijos amplios, centro y todo igual. Se cierra esta implementación. 168 muestras, 192 salidas exactas y 4.944 comprobaciones previas. [[E060 - Prerregistro cuatro rangos]]. [Matriz y trabajo lógico](../results/e060_four_ranges/summary.md).

El recuento de las 28 trazas de E058 encuentra, por mediana, solo 5–7 tramos terminales de hasta 32 claves por ordenación de 10M y cero pares de hermanos de ese tamaño. El 93,3% de las claves termina en tramos de 65–128. Esto descarta priorizar lotes limitados a hojas muy pequeñas con el árbol actual. [Análisis reproducible](../analyze_e058_leaf_sizes.py).

E061 cronometra aproximadamente una de cada 16 llamadas a la red terminal de vqsort, con alineación de 64 B y vqsort limpio como control. Todas las hojas suman 9,08–9,29 ms corregidos y las de 65–128 suman 8,46–8,65 ms. El modelo ideal de un lote de ocho da 7,40–7,57 ms frente a los 9,01–9,37 ms necesarios. Las cuatro entradas descartan agrupar directamente las hojas de 65–128 con el árbol actual. 56 tiempos y 112 salidas exactas. [[E061 - Prerregistro presupuesto de hojas]]. [Matriz](../results/e061_leaf_budget/summary.md).

E062 representa cada aparición por su posición, forma hasta ocho planos y materializa la salida desde un auxiliar de 512 claves. Al repetir los mismos tramos naturales de hasta 512, cubre las 10M claves con unos 28.450 tramos por ordenación. Los mapas tardan 104,15–105,35 ms frente a 18,01–18,78 ms de repetir vqsort sobre esos tramos. Pierden por 85,72–86,73 ms de mediana pareada en las cuatro entradas y se cierran en el filtro. Vqsort directo tarda 45,70–47,72 ms. 84 tiempos, 96 salidas de brazos y 32 capturas exactas, más 4.168 comprobaciones previas. El ensayo es de repetición de tramos y la métrica decisiva es contra el control local. [[E062 - Prerregistro mapas por posición]]. [Matriz y muestras](../results/e062_position_bitmap/summary.md).

E063 intercambia posiciones mal colocadas y omite vectores correctos. En las cuatro entradas prioritarias, reduce las escrituras proyectadas de unos 329–330M a 167–169M posiciones, pero los lotes pasan de 5,46–5,74 a 12,13–15,13 ms. El ahorro proyectado es negativo en todas, con pérdidas de 78,34–85,72 ms bajo el modelo por clases. Pierde con pivote 95/5. Solo gana en datos ya separados, por 1,00–1,23 ms pareados y cero escrituras. Se cierra el filtro. 1.036 tiempos por lote o completos, 29.376 particiones exactas con calentamientos, 32 vqsort completos y 4 capturas exactas, 1.836 particiones de telemetría y 8.224 comprobaciones previas. [[E063 - Prerregistro intercambio de bloques]]. [Matriz y muestras](../results/e063_exchange_partition/summary.md).

E064 mide una frontera natural de 444–448 tramos de hasta 32.768 claves. Cuesta 28,14–28,74 ms dentro del árbol y 29,30–29,82 ms al repetirla. El brazo optimista con una copia preparada cuesta 32,52–33,25 ms. Quedan 3,61–4,24 ms hasta la meta en las cuatro entradas. 112 tiempos, 128 salidas de brazos y 32 capturas exactas. [[E064 - Prerregistro presupuesto de reparto]]. [Matriz](../results/e064_distribution_budget/summary.md).

E065 cobra reservar y llenar un auxiliar nuevo de 40 MB, copiarlo al array, finalizar los mismos tramos y liberar. Tarda 60,68–62,29 ms frente a 32,60–33,46 ms con una copia preparada y 45,45–46,93 ms de vqsort completo. Excede el objetivo en 24,04–24,82 ms en las cuatro entradas, antes de detección y clasificación. Se cierra la secuencia de dos materializaciones separadas con auxiliar de tamaño completo y esta frontera. 140 tiempos, 160 salidas de brazos y 32 capturas exactas, cero respaldos. [[E065 - Prerregistro doble materialización]]. [Matriz](../results/e065_staging_budget/summary.md).

E066 usa el reparto por bloques de IPS2Ra y finaliza con vqsort por rango. Los cuantiles adaptativos consiguen 512 rangos en las cuatro entradas prioritarias, pero elección y reparto cuestan 22,93–26,86 ms. En uniforme pierde frente a los nueve bits fijos y en prefijos amplios gana a ese control. Frente a vqsort completo da 0,868–0,962× y falla el filtro. Pierde con cubeta dominante y detecta `dense16` antes de repartir. 168 tiempos, 192 salidas exactas y 170 comprobaciones previas. [[E066 - Prerregistro reparto in situ por bloques]]. [Matriz](../results/e066_inplace_blocks/summary.md).

E067 separa las fases de E066 en uniforme y prefijos amplios. En el adaptativo, clasificar y llenar buffers cuesta 13,32–17,24 ms, permutar 6,78–7,66 ms, márgenes unos 0,03 ms y el resto 0,72–0,79 ms. Suprimir la clasificación entera aún deja `prefix_distinct/42701` a 1,72 ms de la meta, y solo da 0,54–1,53 ms de margen en las otras tres. Suprimir cualquiera de las otras fases queda corto en las cuatro. Es una resta por ronda con el resto de trabajo fijo. Se cierra la optimización aislada de una fase. 84 tiempos, 96 salidas exactas y 170 comprobaciones previas. [[E067 - Prerregistro fases de bloques]]. [Matriz](../results/e067_block_phases/summary.md).

E068 reparte por ciclos con la tabla adaptativa de E066 y límites de cubeta preparados. El contador confirma una escritura lógica por posición inicialmente incorrecta. El reparto cuesta 95,24–100,71 ms en uniforme y 62,73–62,76 ms en prefijos amplios. Pierde en las cuatro entradas frente a bloques con los mismos límites y vqsort directo. En `dominant` gana al reparto por bloques y pierde frente a vqsort. En `grouped` solicita cero escrituras y termina en 34,94–35,00 ms frente a 50,94–51,42 ms de vqsort, con los límites preparados. Se cierra el filtro general. 168 tiempos y 192 salidas exactas contando calentamientos, más ocho pasadas de telemetría exactas y 7.830 comprobaciones previas. [[E068 - Prerregistro reparto por ciclos]]. [Matriz](../results/e068_cycle_partition/summary.md).

E069 aplica radix local 12+12 a los desplazamientos de los tramos naturales de hasta 32.768. Acepta las 10M uniformes y el 99,3% de prefijos amplios. Ahorra 1,72–1,88 ms frente a repetir los finalizadores vqsort en uniforme y pierde 9,77–10,17 ms en prefijos amplios. Falla la meta de 9,27–9,53 ms de ahorro. 84 tiempos, 96 brazos y 32 capturas exactas. [[E069 - Prerregistro radix local de 24 bits]]. [Matriz](../results/e069_radix24/summary.md).

E070 hace un reparto por byte del desplazamiento, ordena sufijos de 16 bits y expande AVX2 al array. Pierde 4,09–4,27 ms en uniforme y 51,30–52,64 ms en prefijos amplios frente a repetir vqsort en la misma frontera. La cobertura coincide con E069. Se cierra el filtro. 84 tiempos, 96 brazos y 32 capturas exactas. [[E070 - Prerregistro sufijos locales de 16 bits]]. [Matriz](../results/e070_suffix16/summary.md).

E071 mantiene partición SIMD y hojas nativas con pivotes aritméticos locales. Ahorra 4,38–4,49 ms en uniforme y 5,02–5,13 ms en prefijos amplios frente a los mismos finalizadores de vqsort. Falla la puerta de 9,37–9,47 ms de ahorro. Los cortes cambian el árbol inferior y un corte sesgado puede respaldar dentro de un tramo aceptado. 84 tiempos, 96 brazos y 32 capturas exactas. [[E071 - Prerregistro pivote aritmético local]]. [Matriz](../results/e071_midpoint/summary.md).

E072 limita el radix local a 256 destinos por pasada. Tarda 124,66–126,27 ms en uniforme y 117,71–118,59 ms en prefijos amplios, frente a 30,02–30,65 ms de repetir vqsort. Pierde 87,10–95,86 ms de mediana pareada con la misma cobertura de E069. Se cierra el kernel. 84 tiempos, 96 brazos y 32 capturas exactas. [[E072 - Prerregistro radix local por bytes]]. [Matriz](../results/e072_radix8/summary.md).

Siguiente contraste general. E071 es el mejor ahorro consistente de E069–E072 y aún le faltan 4,24–5,06 ms. Separar el coste de partición y red terminal, registrar volumen clasificado y contar los cortes que activan respaldo con ambos lados no vacíos. Solo en esos casos se puede conservar un corte ya pagado ordenando ambos lados por separado. Medir el presupuesto de esos respaldos antes de cambiar el kernel y exigir el ahorro acumulado de la misma puerta. La fusión del segundo corte y conteo de E056 en 50/50 queda en segundo plano. [Matriz E071](../results/e071_midpoint/summary.md).

Para alta entropía quedan pendientes otros mecanismos tras el reparto de E055 y las hojas compactas de E052. F5 sigue sin medición local. La página de IRL remite al autor para obtener el código. Para baja cardinalidad siguen pendientes la prioridad en few_dominant y la reutilización exacta del prefijo contado ante rechazo tardío. [[26 - Meta del 25 por ciento y hojas compactas]]. [[27 - Diccionario exacto para pocas claves]]. No queda trabajo en ejecución. [Página de IRL](https://irl.cs.tamu.edu/projects/streams/).

## E052–E053

El objetivo acordado es 1,25× de velocidad por caso principal a 10M frente a la referencia más rápida de la tanda, con todo el coste incluido. E052 descarta las hojas de 16 bits para el residual y el uniforme. A 10M uniforme tarda 80–81 ms frente a 47–48 ms de vqsort. El control de mismo reparto de 32 bits queda cerca. El error del analizador de claves por hoja se corrigió y la matriz se completó con el mismo binario. [[26 - Meta del 25 por ciento y hojas compactas]].

E053 aborda pocas claves dispersas con proyección por bits, comprobación de pertenencia exacta y conteo. [[E053 - Prerregistro diccionario por bits]].

E053 pasa el filtro de baja cardinalidad con 1,54–1,67× frente a vqsort. El rechazo tardío añade 3,35–4,67 ms. E054 mide el compuesto de ventanas y diccionario frente a las tres referencias fijadas y controles internos. [[27 - Diccionario exacto para pocas claves]].

## E048–E051

2026-11-05. E047 sigue como candidato general. Leer [[25 - Compactación y separación in situ]] para E048–E051. Las variantes preparadas no superaron sus puertas para extender la cobertura a 50/50 aleatoria. E048 acelera la clasificación aleatoria pero pierde una periódica. E049 elimina unos 20 MB de buffer en 50/50 a 10M, pero pierde frente a vqsort. E050 usa un cursor y gana 2,5–3,4% con ventana preparada. E051 lleva la mejora preparada a 7,5–8,1%, con pérdidas de 20–23% en 95/5 frente a separación escalar con buffer. Su modo de fases da 10,40 ms de clasificación, 21,72 ms de sort residual y 1,54 ms de reconstrucción en una 50/50 aleatoria. Los tiempos internos pertenecen al diagnóstico. El ensamblado confirma la ausencia de salto dependiente de la clase.

No cambiar el presupuesto de E047 con estos resultados. Próximo contraste propuesto, vqsort residual frente a reparto grueso más vqsort por tramos, incluyendo todos los recorridos y la salida final. Aislar sobre residuales de 5M antes de integrar. Hay 1.316 muestras y 1.504 salidas exactas en E048–E051 con calentamientos, y 144 salidas adicionales en modos de fases. Se conservan los negativos y los archivos de reproducibilidad. No quedan procesos en ejecución.

## Secuencia E048–E050

2026-11-05. E048 no promueve la compactación AVX2. Reduce de 29 a 12 ms la clasificación de la mezcla 50/50 aleatoria, con un negativo periódico (6,10 → 7,71 ms). Las pruebas preparadas comparan el mismo multiconjunto y verifican salida, residuo y contadores. E049 ensaya separar bajos y altos hacia los extremos del propio array y emitir multiplicidades en el hueco, con la ventana conocida. La política de E047 permanece intacta. [[25 - Compactación y separación in situ]].

E049 confirma la separación in situ para ventana conocida y falla la puerta de rendimiento. A 10M en 50/50 aleatoria tarda 37,88–38,58 ms frente a 36,67–36,85 ms de vqsort. E050 aísla la alternativa de un cursor hacia delante y separa los tiempos de clasificación, sort residual y reconstrucción. [[E050 - Prerregistro cursor y fases]].

E050 reduce el coste de clasificación aleatoria con el cursor único, pero su ganancia completa preparada de 2,5–3,4% queda por debajo del objetivo de 10%. El diagnóstico separa 12,23 ms de clasificación, 21,59 ms de sort residual y 1,53 ms de reconstrucción. E051 cambia la clasificación por un coste fijo por clave y añade el adversario de un externo repetido. [[E051 - Prerregistro clasificación de coste fijo]].

## Candidato completo E047

2026-11-05. Leer [[24 - Ventanas y certificado]] para el candidato actual. E047 pasó el filtro prerregistrado en 20 entradas y completó el sorter frente a vqsort, x86-simd-sort e IPS2Ra con el mismo binario. El filtro emparejó estados iniciales de vqsort, la comparación completa usó el estado habitual. A 10M ganó ambas semillas de dense16, skew y bimodal frente a las tres referencias, con 1,68–2,81× frente a la más rápida por entrada. También ganó ambas intercalaciones de dos ventanas. 14/24 menores medianas en 1M y en 10M, incluidas diferencias pequeñas de la ruta de respaldo. La mejora medida es para ventanas densas y datos sesgados o multimodales que caben en ellas. Uniforme, mixed y prefijos amplios delegan. La comparación completa conserva pérdidas en equal, few y casi ordenado. El rechazo tardío a 10M cuesta 1,87–3,23 ms adicionales a vqsort. [Matriz completa](../results/e047_windows_full/summary.md).

La entrada del candidato es `supersort::window_e047_u32(a, n)`. Mantiene el contrato, escribe en el array original y admite duplicados. El certificado acota el rechazo a n+32 lecturas lógicas más probe antes de delegar. En la rama admitida conserva multiplicidades exactas y ordena solo externos. Reserva hasta 512 KiB más cuatro bytes por externo, con máximo floor(n/8) externos. La implementación medida usa AVX2 en una máquina. No se midieron 100M ni otras arquitecturas. Hay 1.536 salidas exactas en full, 480 en el filtro y 54 comprobaciones previas de E047. El siguiente contraste aísla la compactación de externos antes de alterar la política de cobertura. No queda trabajo en ejecución.

## E045 y E046

2026-11-05. E045 descarta la hoja de tres sufijos en el contraste preparado. A 10M uniformes el residual medido fue de 61.844 y 62.086 claves y la hoja tardó aproximadamente 2,5× lo que tarda copiar y ordenar con vqsort local. El adversario abortó los 256 grupos en su última clave. La recuperación del mismo binario tras una excepción de acceso nativa deja 15/18 entradas completas. Conservar muestras, guardas y fallos. [[23 - E045 celdas descartadas]].

E046 formula el conteo por una o dos ventanas con certificado exacto, una ruta de rechazo que mantiene A intacto y ordenación de las claves externas. El prerregistro separa su filtro causal de la comparación condicionada frente a las tres referencias externas. [[E046 - Prerregistro ventanas]].

E046 midió ganancias de 1,71–2,62× en dense16, skew y bimodal frente a vqsort, pero falló el filtro por equal y un few. E047 prepara un certificado por bloques para constantes y aísla el coste de bypass con el mismo estado inicial de vqsort por ronda. Conservar ambos experimentos y exigir su propia puerta. [[E047 - Prerregistro certificado por bloques]].

## Contexto anterior a E045

Actualizado el 2026-11-05 tras E042–E044 y una sesión de razonamiento sin pruebas. E044 sigue siendo la última tanda experimental. No se lanzaron compilaciones ni benchmarks en la sesión de análisis.

## Punto de continuación

El usuario aclaró que la prioridad es un sorter general para datos aleatorios de distintas distribuciones, con exactitud para cualquier entrada `uint32` válida. Leer primero [[22 - Relevo para un sorter general]]. Retomar la búsqueda de un mecanismo que ahorre trabajo con coste acotado cuando falla. La reparación por certificados de [[19 - Rutas alternativas]] y [[21 - Decisión tras el análisis]] se conserva como vía secundaria para arrays casi ordenados. El caso E043 de veinte intercambios a 10M tiene D≤40. La garantía es de corrección y escrituras lógicas, no de tiempo ni de utilidad para aleatoriedad general.

[[20 - Diseño de celdas ordenadas]] desarrolla la tabla local de 256 KiB con tres sufijos crudos y época. Espera unas 62.149 claves de residuo solo bajo el modelo uniforme independiente a 10M. El fallback exacto por grupo es parte del diseño y debe pagar sus intentos fallidos. El negativo E007 ya ordenaba explícitamente solo duplicados. La hipótesis de mejora exige justificar localidad y emisión y sobrevivir a prefijos concentrados y mezclas de distribuciones. Los adversarios y las condiciones de descarte están documentados. Ninguna de las dos candidatas ha sido implementada ni medida. La mezcla SIMD queda como vía de ingeniería separada.

- **E042** separó trabajo y tiempo. Cero fallback en doce entradas y 216 salidas instrumentadas exactas. En las nueve que usan redes, quick128 añade volumen de partición de aproximadamente 1,000–1,116 veces n y elimina las hojas de 129–256. Few/equal/alternating registran cuentas idénticas y cero redes. Las seis pérdidas fuertes antiguas no reaparecen en las medianas de 96 procesos, pero hay cambios de ganador entre bloques. Se mantienen los negativos E040/E041. El sanitizador inicial se atascó con DEADLYSIGNAL en la segunda entrada vacía. El host persistente noPIE con las mismas bibliotecas sanitizadas completó 7464 comprobaciones exactas sin stderr. [[13 - E042 trabajo y variación]].
- **E043** midió el mismo binario a 100k, 1M, 10M y 100M. A 10M, quick128 gana 17/20 ante DSO256 y 1/20 ante mejor referencia incluida. A 100M, tres familias y una semilla, gana 2/3 y 0/3. Uniforme 604,556ms, vqsort alrededor de580ms. RSS pico 1148,9–1149,2MiB del proceso completo. [[15 - Escala y contadores]].
- **E044** midió la llamada a las dos bibliotecas E040. 176 llamadas medidas y 192 salidas exactas, 88 controles vacíos. Uniforme 10M registra 6,6% menos ciclos y 11,1% menos fallos genéricos de caché pese a más instrucciones y fallos de rama. Todas las filas tienen el grupo activo al menos 99%. Se mantienen los límites de la PMU de WSL y de una sola arquitectura. [[15 - Escala y contadores]].

**Vía de ingeniería**. El diseño de mezcla AVX2 de ocho claves conserva el árbol Powersort y las copias de E038. La prueba del bloque pendiente, el caso adversario de cola escalar larga y el antecedente de Chhugani et al. 2008 están en [[14 - Diseño de mezcla SIMD]]. Si se retoma, verificar primero red y mezcla con extremos, residuos, offsets y guardas. Luego validar y medir el sorter completo con el mismo árbol en entradas nuevas. El diseño aún espera implementación y medición.

La revisión científica y la síntesis del reto están en [[11 - Literatura y límites de novedad]] y [[12 - Síntesis del reto y candidatos]].

## Intención del usuario y continuidad

El usuario quiere investigación razonada para mejorar quicksort/mergesort en CPU: hipótesis de costes, adaptatividad, memoria y pruebas verificables, no búsqueda a suerte. Pidió **no detenerse al final de cada episodio**: encadenar etapas justificadas, actualizando notas y preregistrando cada contraste antes de medir. No prometer ejecución entre turnos; seguir cada proceso explícito hasta terminar. Se avisó de este punto de compacción después de varias etapas.

Leer AGENTS.md, [[00 - Mapa]], [[01 - Contrato experimental]], [[05 - Estado actual]], [[06 - Correctitud y límites]], [[09 - Lecciones árbol ramas y hojas]] y [[10 - Diagnosticar variabilidad antes de adaptar]].

## Hallazgo actual: quicksort con hoja menor, todavía experimental

**quick128** cambia únicamente `avx2_vector<uint32_t>::network_sort_threshold` de 256 a 128 en una copia privada del x86-simd-sort fijado a `6e059b14975df2e3c74260ec905167a1be5a34ca`. Pivote, partición, iguales, max_iters y fallback permanecen como upstream. No modifica int32/float ni el vendor original. No usar XSS_MINIMAL_NETWORK_SORT, que cambiaría a ocho.

Control causal **simd256dso**: original sin cambios dentro de otro DSO, con las mismas flags PIC/visibilidad y APIs C únicas. `quick_support.py` comprueba delta byte-exacto, static_assert, hashes y exportaciones readelf; archiva fuentes, bibliotecas, licencias, mapas y logs. El simd original integrado en el host también se compara siempre.

### E040: resultado inicial

[[E040 - Prerregistro umbral quicksort]] y [análisis](../results/e040_quick_holdout_linux/analysis-quick.md).

- Gana 16/16 entradas uniform/SplitMix tanto al control DSO256 como al SIMD del host. Frente al host: 1.078–1.120x, dentro de esta serie.
- Gana 53/176 casos nominales frente a la mejor referencia externa incluida; no victoria general.
- Falla robustez: n=8193, skew, semilla33013, ratio control/candidato=0.898323, aproximadamente 11.3% más lento. Conservar este negativo.
- Ensamblado exacto archivado: red ascendente de 32 vectores, 30487 bytes y 1173 instrucciones vectoriales estáticas con referencia a rsp; red de 16, 9993 bytes y 125 referencias. No contar rbp como pila sin probar que es framepointer. No son conteos dinámicos de spills, DRAM ni ciclos.
- Correctitud: 6336 salidas iniciales y 21120 de rendimiento; ASan/UBSan y guardas: 6624 casos extra, sin diagnósticos de ejecución.

### E041: holdout con el MISMO binario

[[E041 - Prerregistro holdout mismo binario]], [holdout](../results/e041_quick_holdout_exact/analysis-quick.md) y [diagnóstico separado](../results/e041_quick_problem_recheck/analysis-quick.md).

`run_existing.py` no compila: verifica snapshots, ejecutable y los DSOs enlazados antes/después y ejecuta procesos nuevos como el runner original. Conserva warmup, orden aleatorio, afinidad, región medida y comprobación exacta.

- Nuevos tamaños 8209/180013/1500007, semillas14009/41011/58013, 22 distribuciones, once repeticiones; 198 nominales, como máximo 180 arrays distintos porque equal/alternating/plateaus repiten datos con las semillas.
- Gana 17/18 uniform/SplitMix. **Falla el criterio estricto** en 180013/SplitMix/14009: control/candidato=0.985329, host/candidato=0.945620.
- **Falla robustez** en 180013/few/58013: ratio=0.896836. Hay otros negativos importantes en forced; leer toda la tabla, no solo los criterios.
- Gana 66/198 nominales frente a mejor referencia externa. No promover universalmente ni retocar tamaño/umbral para excluir fallos.
- 21780 muestras y 23760 salidas exactas.

Recheck preregistrado, no independiente: n=8193, semillas12007/33013, skew/uniform/dense16, 51 repeticiones, mismos diez algoritmos. 3060 muestras y 3120 salidas exactas. El fallo original skew/33013 **no se reproduce**: ahora ratio DSO/candidato=1.121 y host/candidato=1.109. No borra E040 ni rescata E041. No más reintentos según resultado. Recompilar no era condición necesaria para cambiar el tiempo; esto no identifica allocator, ASLR, caché, frecuencia ni otra causa.

## E038/E039: lecciones que conservar

- E038: árbol ponderado frente a parejas, misma formación natural128 y mismo ejecutor std::merge+copyback. Tabla estructural exacta, gana 16/16 forced_front/middle por 1.279–1.554x y pasa límite de sobrecoste random del 10%. Tail es negativo con volumen igual. Solo 2/176 ante mejor referencia. [Análisis](../results/e038_tree_holdout_linux/analysis-tree.md).
- E039: mismo árbol, kernel de selección por booleanos/cmov. ASM confirma selección sin rama de datos; contadores idénticos 176/176. Random gana 16/16 apenas 1.009–1.028x, pero few llega a ser 3.89x más lento y robustez falla. 0/176 ante mejor referencia. No sustituir globalmente ni añadir selector para rescatar la tabla. En equal C_exec=0: sus diferencias no prueban coste de cmov. [Análisis](../results/e039_kernel_holdout_linux/analysis-kernel.md).

## Antecedentes todavía relevantes

- E030/E033: mejora de buckets predictivos + SIMD en un nicho uniforme mediano; cifras de tandas distintas no se mezclan.
- E034: selector fijo gana 19/20 uniformes del rango por sistema, falla criterio estricto; K1280 secundario valida cuatro entradas de129k por entorno. No sustituir al principal retrospectivamente.
- E035: hoja129/128 cuesta 3.166x Windows y 3.364x Ubuntu en microbenchmark distinto del contrato completo. Motivó E040, no lo validaba por sí sola.
- E036/E037: mergesort escalar simple no competitivo; detectar runs reduce niveles pero puede aumentar mezcla real. E038 aisló el árbol para entenderlo.
- E026 y nuevas variaciones siguen sin explicación causal. E027 no respalda culpar directamente a malloc/free caliente. No declarar arreglado por noinline, caché ni allocator.

## Preguntas de la propuesta original E042

Leer [[10 - Diagnosticar variabilidad antes de adaptar]] para motivación y [[13 - E042 trabajo y variación]] para resultados. La propuesta separó:

1. Trabajo algorítmico: particiones, tamaños de hojas, detección de orden/iguales, profundidad, fallback a std::sort y elementos de fallback, en copias instrumentadas separadas.
2. Variación entre procesos/rondas: direcciones y condiciones de ejecución, con rondas y datos fijados de antemano. Instrumentación fuera del ranking; no usar sus tiempos para ganar.

Incluir fallos y controles positivos, conservar ambos resultados del recheck y no seleccionar semillas favorables. Los binarios de rendimiento de E040 permanecen intactos. No barrer umbrales ni introducir selector para ocultar fallos. Otra vía posterior es mezcla SIMD con invariante/colas demostrados antes de medir, no otro ternario escalar. Integrar quick128 en buckets sería un nuevo candidato y necesitaría su propia validación.

## Protocolo y herramientas

CPU uint32 sin payload, un hilo. Reserva, inicialización necesaria y copia final dentro del tiempo completo; generación/copia común/comprobación exacta con std::sort fuera. Orden aleatorio por ronda y warmup. No compilaciones ni cargas intensivas concurrentes con benchmarks; no modificar fuentes durante compilación. Etiquetas nuevas, CSV inmutables, no descartar semillas.

Windows/GCC16.1 y Ubuntu WSL/GCC11.4 son series distintas; afinidad virtual CPU2 no implica el mismo núcleo físico. Frecuencia/carga de fondo y direcciones no controladas completamente. Últimas etapas E038–E041 solo Linux/AVX2, no generalizar a otro hardware o contratos.

- `run.py`: fuentes/hashes/metadatos; `--tree-diagnostic`, `--kernel-diagnostic` o `--quick-threshold` según fase.
- `verify_stage.py`: sanitizadores/guardas seriales y fuentes exactas; E040 incluye DSOs instrumentados.
- `analyze_tree.py`, `analyze_kernel.py`, `analyze_quick.py`: principal y controles fijos, tablas por entrada y negativos.
- `inspect_merge.py`, `inspect_quick.py`: binarios y ASM exactos tras terminar mediciones.
- `run_existing.py`: reutiliza binario y rutas a DSOs registradas, verifica hashes. Conservar esas rutas durante la ejecución; las copias y fuentes también están archivadas.
- `e042_work.py`, `e042_process.py`, `e042_recover.py`: trabajo instrumentado, procesos con binarios exactos y recuperación separada de sanitizadores.
- `e043_scale.py`, `e044_pmu.py`: escala con el ejecutable exacto y eventos por llamada a las bibliotecas archivadas.
- `archive_evidence.py`: copia prerregistro/analizador sin sobrescribir. `status.py`: índice de tandas completas.

Acumulado del índice: **279.065 muestras de tiempo y 319.280 salidas completas exactas**. Instrumentación, PMU y sanitizadores van aparte. No hay ningún proceso pendiente ni trabajo autónomo entre turnos.
