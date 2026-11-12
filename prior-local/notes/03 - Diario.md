# Diario

## 2026-11-04 — experimento E001

Hipótesis: una distribución global por bits altos y dos pasadas LSD locales pueden reducir presión de memoria frente a varias distribuciones globales. Probar particiones de 8, 10 y 12 bits altos. El tráfico de copia final y el coste de histogramas por bloque podrían anular la mejora.

Implementación: bench.cpp. Orquestación: run.py con biblioteca estándar, ejecutable usando uv. Referencias externas: pdqsort y ska_sort; baselines propios: LSD8 y LSD11 con histogramas fusionados.

Estado inicial: pendiente de resultados. No hay novedad ni mejora demostrada.

### Resultado del piloto E001

Una semilla (42), cinco repeticiones, uniforme. Para 10 millones: local12 63.952 ms, LSD8 97.864 ms, LSD11 106.475 ms, ska 150.579 ms, pdq 214.709 ms y std 536.821 ms. Para 100.000: LSD11 0.424 ms, mejor que todos los locales. Para 1 millón: local8 6.284 ms vs LSD11 7.500 ms.

Decisión: señal positiva dependiente del tamaño, sin demostrar novedad ni estado del arte. No usar el mejor local retrospectivo como si fuera un selector ya validado. Fuente original y runner conservados en results/e001 junto a CSV y metadatos.

## E002 — fronteras y distribución bufferizada

Añadidos búferes escalares de 16 enteros por bucket para distribución global; comparados tanto en radix LSD como en candidatos locales. No son escrituras no temporales ni una implementación definitiva de distribución bufferizada.

Validación: 13 tamaños (0, 1, 2, 31, 63, 64, 65, 255, 256, 257, 4095, 4096, 4097), siete distribuciones, doce algoritmos, una ronda de calentamiento y otra medida. Las 2.184 salidas se compararon exactamente con std::sort sin fallos. Sus tiempos diminutos no sirven para extraer conclusiones de rendimiento.

## E003 — matriz de robustez

En curso inicialmente: tamaños 1M y 10M, siete distribuciones, semillas 42/137/2026, cinco repeticiones. Conservar resultados negativos y distinguir ganancia por distribución. Próximo paso: SIMD AVX2 competitivo, usando x86-simd-sort commit 6e059b14975df2e3c74260ec905167a1be5a34ca.

### E003 completado

2.520 muestras medidas, 504 rondas de calentamiento adicionales. Correctitud exacta en todas. En 10M uniformes, local12 gana a la mejor referencia incluida por factores 1.51–1.57 según semilla. Pierde en las otras seis distribuciones a ese tamaño. Todo igual: pdq unos 4–5 ms vs local unos 44–47 ms; ordenado: pdq unos 5 ms vs local unos 42 ms. No es candidato universal. Los búferes escalares ensayados empeoran el uniforme grande.

## E004/E005 — referencia AVX2 y contadores compactos

E004: 91 entradas de frontera, 18 algoritmos, 3.276 resultados comprobados contando calentamiento, sin discrepancias. E005: uniforme, 100k/1M/10M, tres semillas, siete repeticiones, 882 muestras medidas.

Resultado decisivo: x86-simd-sort AVX2 gana a los radix locales grandes. En 10M, SIMD 50.26–51.44 ms frente a local8c32 59.56–60.25 ms. El ahorro de contadores de 32 bits mejora nuestros locales, pero no alcanza a SIMD. En 1M también perdemos.

Hallazgo pequeño: en 100k, local10simd (distribución por prefijo seguida de x86-simd-sort por bucket) tarda unos 0.302–0.305 ms frente a SIMD global 0.359–0.374 ms, mejora 1.18–1.24x en las tres semillas. Es selección retrospectiva entre variantes: necesita holdout de tamaños/semillas y referencia radix más fuerte antes de promoción. La idea híbrida tampoco se considera nueva.

## E006/E007 — bitmap jerárquico local

Hipótesis: representar claves presentes en un bitmap con un segundo nivel de ocupación, enumerarlas con ctz y fusionar duplicados de un vector separado permite evitar dos pasadas LSD. No presupone unicidad. Primer reparto por prefijo de 10/11/12 bits, bitmap local de 512/256/128 KiB respectivamente; el mismo espacio se reutiliza y se limpian solo las palabras visitadas. Los duplicados se ordenan con std::sort: comportamiento potencialmente malo con alta repetición.

E006: 84 entradas de frontera, tres variantes, 504 resultados comprobados contando calentamiento, sin discrepancias. E007: benchmark uniforme frente a SIMD y radix, pendiente inicialmente.

E007 completado: 10M uniforme, bitmap 77–82 ms según variante; SIMD global 49–51 ms. Descartar esta implementación por ahora, aunque es correcta. No ha reducido el tiempo pese a eliminar pasadas LSD.

## E008/E009/E010 — delimitar la victoria pequeña

E008: tamaños y semillas nuevos. Híbrido local10simd prometedor alrededor de 100k; SIMD global gana en 16k y 1M. E009: afinidad Windows a CPU lógica 2, 31 repeticiones, cinco semillas nuevas, cuatro tamaños. Para candidato fijo local10simd y 100k: factores de mejora 1.403, 1.394, 1.368, 1.348, 1.364 frente a la mejor referencia incluida (SIMD en los cinco casos). Tiempos 0.242–0.247 ms vs 0.331–0.341 ms.

La ventaja NO se traslada limpiamente a 65.536, 131.072 ni 262.144. Incluso con afinidad hay variabilidad entre entradas y asignaciones: estudiar umbrales de redes SIMD, alineamiento, ocupación por bucket y caché. No atribuirla automáticamente a ruido ni ocultarla.

E010: 100k, seis distribuciones no uniformes, tres semillas, 21 repeticiones. local10simd pierde en todas frente a la mejor referencia de esa entrada. Así que la mejora observada es de un nicho uniforme de tamaño concreto, no de un sorter general.

## E011/E012 — buckets de capacidad prevista

Idea: evitar el histograma inicial reservando 1.024 buckets de capacidad fija. Capacidad = media + slack * sqrt(media) + 16, redondeada a múltiplo de 16. Probar slack 2/4/6. No se garantiza estadísticamente ausencia de overflow: se comprueba cada inserción y, al desbordarse, se ordena el array original intacto mediante SIMD global. Por tanto, la corrección no depende de distribución ni de probabilidades. El fallback se incluye en el tiempo.

La reserva y la inicialización del espacio con huecos se incluyen. Al terminar el reparto se ordenan buckets con x86-simd-sort y se concatenan. Memoria adicional proporcional a capacidad * 1.024, superior al vector de scratch exacto. No afirmar novedad: es una variante de bucket sort con espacio sobrante y fallback.

E011: 49 casos incluyendo vacíos, fronteras pequeñas y 100k en siete distribuciones; tres variantes y dos rondas: 294 resultados exactos, incluyendo distribuciones que fuerzan el fallback. E012 en marcha: uniforme 65k..10M, cinco semillas, once repeticiones.

### E012–E015 — primera mejora práctica acotada

E012: predict10s4 gana a la mejor referencia incluida en 65k, 100k y 131k para las cinco semillas. En 100k los factores son 1.62–1.69x. Pierde en 262k, 1M y 10M. No generalizarlo a n grande.

E013 usa semillas nuevas (271, 811, 1601, 4099, 65537), dos generadores (mt19937_64 y SplitMix64), tamaños 80k/100k/120k, 31 repeticiones y afinidad CPU 2. predict10s4 supera las medianas de todas las referencias incluidas en las 30 entradas. La ganancia de algunas entradas en 80k es apenas 1.04x y podría no ser significativa.

Extraído el candidato a include/supersort/predictive_u32.hpp, función supersort::predictive_u32(ptr,n), parámetros predeterminados H=10 y Slack=4. Usa x86-simd-sort como dependencia: no es un kernel SIMD original. E014 valida el header en 80 entradas, calentamiento y medición, sin discrepancias. E015 repite la confirmación tras extraerlo: 6.510 muestras, 30 entradas. También gana por mediana en las 30, con mínimo 1.013x que NO debe venderse como mejora robusta por sí solo. En las diez entradas de 100k el mínimo es 1.133x y máximo 1.747x. Hay variación importante dependiente de entrada o layout que falta explicar.

Estado honesto: mejora empírica localizada sobre x86-simd-sort AVX2 y radix propios, no superioridad sobre todo el estado del arte ni algoritmo nuevo. Faltan vqsort e IPS2Ra; tampoco se ha aislado el efecto de asignadores/caché.

## 2026-11-05 — E016/E017, extensión a n grande

El usuario pide continuar en este chat al primer punto de relevo. Próximo intento: capacidad prevista con más buckets (12/14/16 bits) y distribución en dos niveles. Primer nivel exacto por histograma y scatter a vector; segundo nivel de buckets con capacidad prevista reutiliza un scratch pequeño por bloque, ordena con SIMD y escribe inmediatamente en el array final. Si un bucket fino desborda, fallback SIMD sobre el bloque grueso original intacto. Se permite fallo de predicción sin comprometer el resultado.

E016: 80 entradas, diez variantes nuevas, 1.600 resultados exactos contando calentamiento, sin discrepancias. E017: tamaños 262k/1M/10M, ambos generadores, tres semillas, cinco repeticiones, en curso inicialmente.

### E017 completado

1.080 muestras medidas. Ninguna extensión muestra una victoria convincente sobre SIMD global. En 10M la mejor variante de dos niveles ronda 54 ms frente a 50 ms SIMD; en 1M las extensiones también pierden. La distribución adicional cuesta más de lo que recupera la ordenación local.

## E018 — elevar baselines

Integrados vqsort de Google Highway (puente con despacho estático nativo) y ska_sort_copy con scratch y copia final si el API indica resultado en buffer. E018: 80 entradas, tres algoritmos, 480 resultados exactos contando calentamiento, sin discrepancias. Falta comparar rendimiento antes de mantener afirmaciones sobre el candidato.

## E019 — software write combining con stores no temporales

Los búferes escalares anteriores usaban stores ordinarios. Nuevo scatter_nt agrupa 16 uint32 por bucket y emite solo líneas completas alineadas a 64 bytes con dos stores AVX2 no temporales. Prefijos y colas parciales usan copia ordinaria para no pisar buckets vecinos. sfence al terminar antes de leer el destino. Se ensaya tanto en baselines LSD como en candidatos locales y de dos niveles: misma optimización disponible para las referencias propias.

E019 valida especialmente longitudes alrededor de 16/32/64 y distribuciones sesgadas. No asumir rendimiento ni corrección de stores por el mero hecho de compilar: comparar arrays completos.

E019 completado: 152 entradas y ocho variantes, 2.432 salidas exactas contando calentamiento, sin discrepancias.

## E020 — comparación con vqsort y radix NT

18 entradas: 100k/1M/10M, MT y SplitMix, tres semillas, siete repeticiones, CPU lógica 2. 1.764 muestras.

La victoria pequeña sobrevive a vqsort: predict10s4 gana en las seis entradas de 100k frente a la referencia más rápida, ahora vqsort. Factores 1.083–1.415x. No usar ya los factores de E012 sin aclarar que las referencias eran más débiles.

En 1M sigue ganando vqsort (~3.94 ms). En 10M vqsort ronda 49–50 ms; dos niveles + NT llegan a 47–51 ms pero sin victoria consistente entre semillas. Nuestro LSD11 NT reduce el coste frente a LSD11 ordinario, pero tampoco gana consistentemente a vqsort. Las escrituras NT son una mejora de implementación conocida, no una innovación reclamada.

## E021/E022 — evitar una copia global de salida

Variante local radix con scratch reutilizado del tamaño del bucket grueso más grande: tmp global -> scratch local (LSD bajo) -> array final (LSD alto). Elimina la copia tmp -> array final tras cada bucket. Reserva e inicializa ese scratch dentro del tiempo; memoria auxiliar adicional O(max bucket), potencialmente O(n) bajo sesgo. Se ensaya H=8/10/12 con scatter NT y contadores uint32.

E021: 104 entradas, tres variantes y dos rondas, 624 salidas exactas. E022: uniforme y SplitMix, 1M/10M, tres semillas, siete repeticiones, en curso inicialmente.

E022 completado: la eliminación de copia no logra una victoria sostenida. vqsort gana en todas las entradas de 1M y en cinco de seis de 10M; una selección retrospectiva gana ~5.6% en una entrada. No promover a sorter grande.

## E023/E024 — layout y memoria sin inicialización innecesaria

Hipótesis: el stride fijo de buckets puede interactuar con los conjuntos de caché; probar un número impar de líneas por bucket y un desplazamiento adicional de un uint32 entre buckets. Son hipótesis de microarquitectura, sin atribuirles todavía las diferencias entre semillas.

Otra variante evita inicializar los huecos de scratch que nunca se leen. Solo los slots escritos antes se pasan al kernel SIMD. La reserva se sigue midiendo; cambia la inicialización, no el límite de medición. Comprobar distribuciones que fuerzan fallback y tamaños de frontera antes de medir.

E023: 104 entradas, cinco variantes, 1.040 salidas exactas contando calentamiento. E024: 30 entradas, nueve algoritmos, 8.370 muestras. Memoria sin inicialización aporta normalmente unos pocos puntos porcentuales; no prueba que explique la variabilidad anterior. El stride desplazado +1 uint32 es mejor en algunos tamaños, sobre todo 131k; el stride impar no gana de forma uniforme. No atribuir causalidad a caché sin profiling.

Seleccionado ANTES del siguiente holdout: predict10shiftraw, parámetros H=10, Slack=4, Padding=2, Uninitialized=true. No seleccionar por entrada después. Es un candidato de rango 65.536–131.072; fuera de ahí no tenemos evidencia de victoria.

## E025/E026 — selector conservador

adaptive: fuera de 65.536–131.072 llama a vqsort. Dentro, examina 256 muestras estratificadas y cuenta prefijos de 10 bits. Si un prefijo aparece más de ocho veces en la muestra, llama a vqsort. Si las muestras son monótonas, verifica el array completo antes de devolverlo o invertirlo. En otro caso usa predict10shiftraw. El fallback de capacidad de predictive sigue siendo independiente y exacto.

Nuevos adversarios: muestras ascendentes dentro de datos aleatorios (sampletrap), una distribución concentrada con muestras uniformes que ocultan el sesgo (samplemiss), un único prefijo con muchos valores (prefixcluster), casi ordenado con swaps. Estos casos verifican que la muestra no se use como prueba de que el array esté ordenado o la predicción sea correcta.

E025: 156 entradas y dos rondas exactas, sin errores. E026: 144 entradas nuevas, siete algoritmos, 21 repeticiones, 21.168 muestras. El selector evita grandes pérdidas en datos concentrados y verifica bien muestras engañosas, pero aparecen regresiones importantes en algunas entradas uniformes (por ejemplo 130k, MT semilla12347: ~0.691 ms frente a vqsort ~0.455 ms). NO promoverlo. Casi ordenado también pierde ante pdqsort. Las mejoras anteriores son evidencia de un nicho, no robustez del dispatcher.

Siguiente: diagnóstico por fases, direcciones módulo4096 y reserva/liberación. Hipótesis alternativas: coste del asignador y page faults, layout/caché, kernel SIMD, fallbacks. No afirmar ninguna antes de aislarla. El algoritmo profile imprime a stderr dentro del tiempo total; sus tiempos totales NO son comparables ni deben clasificarse como candidato. Solo se usan sus mediciones internas por fases.

## E027 — primer diagnóstico

En la copia instrumentada la reserva y liberación calientes rondan 0.1–0.3 us, frente a ~80–115 us de scatter y ~110–220 us de sort+copy. Eso no apoya atribuir las regresiones observadas directamente a malloc/free. La copia instrumentada tampoco reproduce todas las regresiones; no permite descartar page faults dentro de scatter ni diferencias de layout/código.

El salto entre 110k y 130k se concentra en sort+copy (aprox. 120 -> 215 us). Hipótesis: buckets de media >~128 activan redes SIMD mayores. Es una inferencia, no un perfil causal validado.

## E028 — kernel compartido sin inlining

Se ensaya una función predict_fixed noinline que llama al mismo kernel seleccionado, y adaptive_fixed que usa exactamente esa función tras el muestreo. Objetivo: distinguir diferencias del código generado al inlining del kernel en dispatcher de problemas de datos/asignación. No cambiar criterios de selección ni escoger ganador por entrada.

E028 completado: las 24 entradas uniformes de ambos generadores ganan con adaptive_fixed por factores 1.336–1.782x frente a la mejor referencia. Pero adaptive original TAMBIÉN mejora en este binario; por tanto no es evidencia causal de que noinline haya arreglado las regresiones. Investigar layout o entorno; no dar el asunto por resuelto.

## E029/E030 — Ubuntu/WSL y referencias IPS

Ubuntu WSL ya estaba instalado y tiene GCC11.4 y TBB. No se instalaron paquetes. IPS2Ra e IPS4o indican no soportar Windows; se usan sus APIs secuenciales originales en Linux, enlazadas con TBB/libatomic y pthread. No OpenMP ni APIs paralelas. Commits: IPS2Ra 83f6b76ca308b277b2acc3a36426a3baa3c9cb73; IPS4o 08a5b926ee65cef19139057c6bde02bb5542c1cb. Fuentes upstream intactas.

E029: 120 entradas, seis algoritmos, 1.440 salidas exactas contando calentamiento. E030 compara 65k/100k/131k/1M/10M, dos generadores y tres semillas, once repeticiones. Comparar SOLO dentro del mismo entorno Linux; la afinidad a CPU virtual 2 no garantiza correspondencia con el núcleo físico fijado en Windows.

E030 completado: 3.300 muestras medidas. adaptive_fixed gana en las doce entradas de 65k/100k frente a la mejor referencia, ya incluyendo IPS2Ra e IPS4o. En 100k: 1.233–1.323x. En 131k pierde en cuatro de seis entradas; el rango alto del selector es excesivo en Linux. En 1M/10M delega en vqsort: ratios cerca de 1 son equivalencia/ruido, NO nuevas victorias. La mejora sobre referencias actuales queda demostrada para ese nicho, no para cualquier n ni para el estado del arte completo.

## E031 — sanitizers

verify.cpp compilado en Ubuntu con ASan y UBSan, -O1 y AVX2 nativo. 1.260 comprobaciones pasan sin diagnósticos: igualdad exacta de kernels predictivos, scatter estable frente a agrupación de referencia y canarios de prefijo/sufijo para offsets 0..15. Incluye longitudes de frontera y cinco distribuciones, uint32 extremos y duplicados. Log en results/e031_sanitizers/verification.txt. No constituye prueba formal ni cubre todo upstream.

## E032/E033 — número de buckets no potencia de dos

Nuevo probe predictive_u32_k<K> con índice floor(uint64(x)*K / 2^32), capacidad prevista y fallback exacto. Probar K=768/1280/1536/2048/12288/24576. Hipótesis: mantener media de ocupación por debajo de los umbrales de redes SIMD sin doblar siempre el número de buckets. La multiplicación y metadatos extra pueden anularlo. No es novedad reclamada; es tuning de bucket sort.

E032: 120 entradas, ocho algoritmos, 1.920 salidas exactas incluyendo calentamiento. E033: Ubuntu, 70k/100k/130k/1M, dos generadores, semillas 1009/12347/99991, 21 repeticiones; 6.552 muestras.

Resultado: K=1280 gana en las seis entradas de 130k por 1.332–1.393x frente a la mejor referencia (vqsort; también se incluyeron x86-simd-sort e IPS2Ra/IPS4o). En 70k también funciona bien (aprox. 1.33–1.36x). En 100k el candidato previo K1024 predict_fixed sigue ganando entre variantes y gana 1.370–1.387x frente a vqsort. En 1M no hay victoria consistente: cinco de seis mejores selecciones retrospectivas pierden; una gana ~4%, insuficiente para promoverla.

K1280 es un nuevo hallazgo exploratorio; necesita holdout, selector preregistrado y vuelta a Windows. No presentar la tabla retrospectiva de mejor variante por entrada como producto final.

Hipótesis para siguiente etapa: modelar coste esperado de hojas SIMD por la distribución de ocupación de buckets (binomial/Poisson), sumando scatter, metadatos y coste por bucket. La librería usa sort_n_vec que reduce el número de vectores recursivamente según N; esto hace plausible un coste escalonado. No basta usar ocupación media: medir fracción de buckets que cruza cada tamaño de red.

## Cierre solicitado por el usuario

2026-11-05: el usuario elige «Compactar y preparar relevo» al segundo punto de control. Terminado E033 y actualizadas notas. No continuar nuevos experimentos en este chat tras el cierre; el próximo chat debe leer 04 - Reanudar y 05 - Estado actual. No hay procesos de benchmark pendientes. Objetivo de investigación general sigue abierto: no afirmar estado del arte universal ni novedad.

## E034 — selector registrado y holdout Windows/Ubuntu

2026-11-05. Ver [[E034 - Prerregistro]]. Principal adaptive_e034: mismo muestreo y rango anterior, K1024 hasta 114688 y K1280 después. Corte heurístico fijado antes de datos, sin ajuste posterior. 144 entradas por entorno; Windows 7 algoritmos/11088 muestras/12096 salidas exactas; Ubuntu 9/14256/15552. Nuevas semillas 2027/7907, seis tamaños incluyendo frontera de selección y salida del rango, doce distribuciones, once repeticiones. Fuentes y metadatos completos en carpetas e034_holdout_*.

No cumple criterio de ganar TODAS las uniformes del rango: 19/20 en ambos entornos. Windows ratio referencia/principal 0.994–1.718 (pierde SplitMix 114689 semilla7907); Ubuntu 0.921–1.351 (pierde uniforme 68000 semilla2027). Secundario preregistrado K1280 sí gana las cuatro de 129k: Windows 1.574–1.694x; Ubuntu 1.105–1.332x. No sustituir retrospectivamente al principal ni promover robustez general.

Fuera del rango, delegar a vqsort pierde mucho frente a pdqsort en sorted: peor ratio 0.150 Windows y 0.086 Ubuntu. Son pérdidas del dispatcher, no una degradación nueva del kernel vqsort ni nueva mejora nuestra. También conservar sampletrap, near_sorted y todos los adversarios en analysis-e034.md. No atribuir anomalías de semillas a allocator/caché sin pruebas.

Nueva dirección explicitada en [[07 - Hipótesis CPU quicksort mergesort]]: separar coste de hojas, partición, política de runs y movimientos. Consultadas fuentes primarias BlockQuicksort y Powersort; ideas conocidas, sin reclamar novedad. E035 mide mecanismo aislado, sin retocar E034.

## E035 — ocupaciones y coste aislado de hojas

Windows y Ubuntu, 21 longitudes preregistradas, 15 repeticiones y calentamiento; 315 muestras por entorno y 172032 hojas verificadas exactamente por entorno. Microcontrato distinto: reserva/copia inicial fuera de tiempo, NO ranking de sorters completos. En Windows 128≈101ns y 129≈321ns. En 129k, K1024 genera 402–428 buckets >128, K1280 solo 5–9 (cuatro entradas). Consultar diagnostic-summary.md para cifras propias de Linux y dispersión. Compatible con mecanismo de redes; no demuestra causa única de regresiones. No se modifica E034. Diagnósticos separados del índice de tiempos completos.

## E036 — mergesort de hojas SIMD y test de orden

Ver [[E036 - Prerregistro mergesort]]: principal merge_skip, control merge_simd. Hojas128, mezcla std::merge ping-pong, copia final y reserva n uint32 incluidas. Sin payload/estabilidad prometida. Corrección razonada del prerregistro ANTES del benchmark: reverse es control negativo porque ordenar hojas no invierte el orden global de los bloques; se conserva criterio original para trazabilidad. No se cambiaron kernels, matriz ni ganador.

Correctitud Linux: 570 entradas, 2 kernels, calentamiento + una ronda: 2280 salidas exactas. Rendimiento Linux: 120 entradas nuevas, nueve algoritmos, once repeticiones: 11880 muestras y 12960 salidas exactas. Se añaden std::stable_sort y tres generadores runs (256/4096/alternancia32-4096), conservando multiconjunto MT antes de ordenar bloques. Fuentes exactas, metadatos, CSV y prerregistro en results/e036_merge_*.

Resultado negativo: merge_skip pierde frente a la mejor referencia en 120/120. Ratio referencia/candidato en uniformes 0.100–0.137 y SplitMix 0.099–0.135. No es competitivo; no promover ni seguir afinando ciegamente la hoja. Test frente a control: sorted 8/8 mejora (1.031–1.971x); near_sorted 8/8 (1.036–2.031x); equal solo 6/8 (0.884–2.253x). En uniform/splitmix ninguna pérdida >5%, pero criterio original no se cumple y tampoco hay ahorro universal en equal. No interpretar min/max de repeticiones como intervalos de confianza.

Inferencia de diseño: saltar comparaciones no evita recorridos/copias ping-pong. Falta aislar experimentalmente cuánto del coste total corresponde a mezcla escalar, hojas y movimientos; no afirmar que sea todo ancho de banda. Siguiente: runs naturales y política de mezcla, con Powersort upstream fijado como referencia, y contraste de kernel separado del árbol. Dejar este resultado negativo conservado. analyze.py reconoce ahora merge* como candidatos propios; analyze_merge.py informa además control y dispersión, sin incluir el control como referencia externa.

Cierre E034–E036: 38364 muestras nuevas de sorters completos y 42888 salidas exactas, aparte de 630 muestras micro y 344064 hojas verificadas de E035. Índice acumulado: 128932 muestras y 146096 salidas completas. No quedan procesos pendientes.

Matiz de referencia E036: las medianas de merge_skip sí quedan por debajo de std::stable_sort en120/120 (stdstable/candidato1.005–3.730). La diferencia mínima es pequeña y puede ser ruido. El prototipo no promete estabilidad con payload y no sustituye a un sorter estable; esa comparación es para claves uint32 del contrato actual. Se conserva esta mejora local sin confundirla con competir con las mejores referencias.

## E037 — runs naturales, fase de correctitud

2026-11-05. Ver [[E037 - Prerregistro runs naturales]]. Principal merge_natural y control merge_fixedruns comparten template de planificador por parejas, std::merge, copia de tramos ordenados y buffers. Solo cambia formación de runs. Descenso estricto antes de invertir; reverse con duplicados puede tener varios runs. Descriptores ceil(n/128) reservados dentro del tiempo en ambos; scratch n uint32 solo si hay más de un run; sin estabilidad/payload.

Powersort original integrado en Linux: commit1d078b6be9023e134c4f8f6de88e2406dc681e89, defaults minRun24/COPY_BOTH, instancia fresca. Reserva/inicialización del buffer y destrucción medidas; sin cambiar algoritmo upstream. Fuentes y MIT conservadas; run.py comprueba commit y árbol limpio y archiva fuentes exactas.

Correctitud e037_runs_verify_linux:874 casos nominales *3 algoritmos *2 rondas =5244 salidas exactas; las2622 muestras temporizadas NO se usan para ranking. e037_runs_sanitizers:2484 comprobaciones exactas con offsets0/1/7/15 y guardas; ASan+UBSan sin diagnósticos de ejecución. Cobertura limitada, no prueba formal.

Se lanza después, sin cargas simultáneas, la matriz de rendimiento fija152 casos nominales, once algoritmos y once repeticiones; el resultado se añadirá al cerrar. Equal/alternating/plateaus ignoran semillas:152 casos nominales son como máximo140 entradas distintas. Diagnóstico posterior a las repeticiones de cada caso; sus dos chequeos extra se contabilizan fuera del índice normal.


### Cierre E037 — resultado y límites

Rendimiento completo:152 casos nominales, once algoritmos,18392 muestras y20064 salidas exactas contando calentamientos. Diagnóstico304 salidas exactas adicionales fuera del índice. Se conservan todos los CSV, snapshots y prerregistro en results/e037_runs_holdout_linux. analyze_runs.py fija principal/control/referencias y verifica que salidas mezcladas+copiadas=n*niveles. No se seleccionó variante por entrada.

Criterio de mecanismo FALLA: sorted/equal/reverse gana8/8 por familia, pero runs4096 solo6/8 (ratios fixed/principal0.992839 y0.997831 en los dos fallos). No rescatar criterio por diferencias pequeñas ni redefinirlo después. Sobrecoste en uniform/splitmix PASA umbral del10%: ratios uniform0.947–1.016 y splitmix0.936–0.981. No es victoria en random; normalmente paga detectar runs.

Run_heavy pierde8/8, ratio fixed/principal0.720–0.822, es decir21.7–38.9% más tiempo. En73001/semilla4243: fixed10 niveles,730010 escrituras de nivel,306637 elementos mezclados; natural8 niveles,584008 escrituras,578023 elementos mezclados. Menos escrituras globales pero más trabajo de mezcla real: coherente con la pérdida, sin atribuir todos los ciclos ni inferir tráfico DRAM. En runs4096 de esa misma longitud:10→5 niveles, pero elementos mezclados342610 en AMBOS; se ahorran copias/hojas, no la fusión superior. Esto explica por qué menos niveles no implica una gran ganancia automática.

Frente a mejor referencia externa, principal solo gana3/152 nominales: sorted73001 ambas semillas y sorted1100009 semilla4243, frente a IPS4o, ratios1.013/1.033/1.061. No hay victoria robusta de familia ni avance competitivo general. Frente a Powersort: gana algunas familias random y pierde todos runs4096/run_heavy; no seleccionar después según distribución. Usar tablas completas para pérdidas y dispersión.

Reverse fragmentado por duplicados confirmado:73001/4243 tiene2 runs;1100009/4243 tiene119, así que no se atribuye a entrada inversa una devolución universal sin mezcla. Sorted/equal sí run1 y0 niveles.

Balance de etapa:21014 muestras completas y25308 salidas exactas nuevas, más304 del diagnóstico y2484 de sanitizadores. Índice global149946 muestras/171404 salidas completas; extras de diagnóstico/sanitizadores aparte. No quedan procesos pendientes. Siguiente E038 todavía NO ejecutada ni preregistrada: [[08 - Árbol de mezclas y movimientos]], contraste de políticas con MISMO ejecutor y datos nuevos. No prometer que Powersort propio será novedad ni mejora garantizada.


## E038 — preparación y correctitud

2026-11-05. Ver [[E038 - Prerregistro árbol ponderado]]. Principal merge_tree_power frente a merge_tree_pair: formación natural128 y ejecutor std::merge+copyback compartidos, solo cambia política del árbol. Planes de ternas adyacentes válidas; poderes por puntos medios diádicos exactos. Mismas reservas de vectores y scratch en ambos. No reclamar novedad (Powersort antecedente); referencia upstream sin cambios.

Forzados con257 runs, uno75% y256pequeños, extremos0/MAX y rotaciones de bloques completos: mismo multiconjunto, fronteras garantizadas y C_exec=C_tree. Análisis PREVIO de longitudes predice reducción~3x front,~2.48x middle, igualdad tail. Tail es negativo obligatorio, no se exige victoria allí.

Correctitud e038_tree_verify_linux:1056 casos nominales,3 algoritmos, dos rondas =6336 salidas exactas;3168 muestras no usadas para ranking. e038_tree_sanitizers:4140 casos con ASan/UBSan, offsets/guardas, sin diagnósticos de ejecución (incluye variantes anteriores y los dos árboles nuevos). Empieza después benchmark fijo de176 casos nominales (como máximo164 datasets distintos). No cargas intensivas simultáneas.

Se registra E039 ANTES de observar tiempos de E038: [[E039 - Prerregistro selección sin rama]]. Cambiará solo kernel de mezcla manteniendo árbol ponderado fijado, independientemente de cuál gane E038. El usuario solicita continuar encadenando etapas sin pedir permiso al cerrar cada episodio. No hay promesa de trabajo después del turno; se seguirán los procesos explícitos hasta terminar.


### Cierre E038 — mecanismo confirmado, no sorter competitivo

176 casos nominales,21296 muestras y23232 salidas exactas completas;352 verificaciones instrumentadas extra. C_tree/C_exec coinciden con TODA la tabla forzada; hashes/runs iguales ycopyback=C_exec. Principal gana16/16 front+middle: front1.279–1.432x y middle1.353–1.554x frente a parejas. Tail, previsto igual en volumen, queda0.972–1.076x: no se exigía victoria. No fallos del umbral10% en uniform/SplitMix. Los tres criterios registrados pasan.

Run_heavy gana8/8 frente a parejas1.292–1.495x y E0371.518–1.686x. Frente a E037 también gana todas las entradas uniform/SplitMix de este binario, pero no equivale a mejorar SIMD competitivo. Mejor referencia externa: solo2/176 nominales ganan (sorted); no promoción general ni novedad. Otras familias tienen regresiones frente al control, incluidas sorted/equal/reverse; tablas completas conservadas.

Análisis en results/e038_tree_holdout_linux/analysis-tree.md, movimientos en tree-movement.md. Se archiva binario exacto, sha256 y ensamblado del ejecutor antes de cambiar fuentes para E039. Copias y planificación dentro de tiempo; no atribuir ciclos ni DRAM a los contadores lógicos. El éxito causal separa política del árbol y ejecutor; E039 cambiará solo kernel, con datos nuevos preregistrados ANTES de estos resultados.


## E039 — kernel, fase de correctitud

Registrado ANTES de tiempos E038. Principal merge_tree_cmov mantiene árbol ponderado y todo el ejecutor salvo selección por clave mediante booleanos/ternario/índices. No se asume branchless por fuente: se inspeccionará ensamblado del binario exacto. Extremos0/MAX válidos sin centinelas; límites comprobados antes de cargar; colas y copyback medidos. Sin estabilidad/payload.

Correctitud e039_kernel_verify_linux:6336 salidas exactas,3168 muestras no clasificadas. Sanitizadores e039_kernel_sanitizers:4968 casos con ASan/UBSan/offsets/guardas, sin diagnósticos de ejecución. Comienza matriz cerrada176 nominales/once algoritmos/once repeticiones, sin otra carga intensiva. Contadores de formación/plan/ejecución deben ser iguales entre kernels; diagnóstico aparte. No se elige candidato tras ver E038.


### Cierre E039 — ramo de selección eliminado, robustez rechazada

176 casos nominales,21296 muestras/23232 salidas exactas, más352 instrumentadas. Hashes y TODOS los contadores de runs/plan/ejecución/copyback/omitidas idénticos176/176. Ensamblado del binario exacto: ejecutor cmov en0x5b00 contiene selección cmovbe/setcc en0x5b7f–0x5b97 y0x5bce–0x5beb, con saltos de límites/loop; std::merge conserva cmp/ja de claves en0x17e9a–0x17e9d. No se infieren fallos de predictor ni ciclos sin contadores hardware.

Criterio de mecanismo pasa (selección sin rama de datos), velocidad random16/16 pasa con ganancias pequeñas: uniform1.009–1.028x, SplitMix1.009–1.026x. Robustez FALLA: few ratios control/candidato0.257–0.290 (~3.45–3.89x más lento); forced_front0.871–0.908, middle0.723–0.761, tail0.887–0.906. Otras pérdidas importantes en near_sorted, reverse, alternating y plateaus. Se conservan TODAS en analysis-kernel.md. Mejor referencia externa0/176 victorias. No promover sustitución universal ni rescatar con selección retrospectiva.

Equal tiene algunas pérdidas>10% aun con C_exec=0: el kernel no se ejecuta allí. No atribuir esas diferencias al cmov ni a mispredicciones; quedan por aislar código generado/layout/entorno de la ruta común. Ganancias random pequeñas no justifican por sí solas añadir selector con coste adicional. Fuente C++ no bastaba para afirmar branchless; se conserva binario y ambos ensamblados.

Sigue E040 ya registrada antes de estos tiempos: [[E040 - Prerregistro umbral quicksort]], una sola modificación de umbral256→128 en copia privada, dos DSOs de referencia/candidato aislados con mismas flags y exportaciones. No ejecución concurrente ni cambios de upstream original.


## E040 — quicksort, fase de correctitud e aislamiento

Registrado antes de ver rendimientoE039. Cambia SOLO umbral AVX2 uint32 de256a128 en copia privada. El resto de fuente/int32/float/pivotes/partición/protección de profundidad intacto. DosDSOs con flagsidénticas/PIC/visibilidadoculta/Bsymbolic/mapaAPIúnica para aislar símbolos; control256 y candidato128. Referencia simdhost también incluida. Originalvendor sin cambios. quick_support.py registra bytes/hash/delta y comprueba sourcefreeze y exportaciones readelf; conserva fuente/licenciaBSD/mapas/logs/bibliotecas.

Correctitud e040_quick_verify_linux6336 salidas exactas (DSOs y simdhost). e040_quick_sanitizers6624 casos con ASan/UBSan, guardas y offsets, incluyendo ambosDSOs y variantes anteriores; sin diagnósticos de ejecución. Se miden después176 casosnominales/10algoritmos/11repeticiones, fuentes yDSOs deO3distintas de los instrumentados, sin cargas simultáneas. Mayor partición frente a menor red es hipótesis falsable del sorter completo; microvictoria E035no bastaría.


### Cierre E040 — quicksort prometedor, un fallo de robustez

176 casos nominales,19360 muestras y21120 salidas exactas completas. Fuente original/privada, delta byte-exacto,DSOs, exportaciones APIúnica, licencias y binario exacto archivados. Principal quick128 gana16/16 uniform/SplitMix frente a simd256dso (uniform1.059–1.143x, SplitMix1.072–1.125x) y también16/16 frente a simdhost (uniform1.078–1.117x, SplitMix1.079–1.120x). Esto sí mejora al quicksort SIMD de referencia en esas entradas, no solo std::sort o radix propio. No reclamar estado del arte ni novedad ni validez para otros tipos/hardware.

Robustez FALLA un caso:8193/skew/33013 ratioDSO/candidato0.898323 (~11.3% más lento). No borrar el negativo ni ajustar umbral. Varias familias con duplicados/plateaus tienen pérdidas menores. Mejor referencia externa53/176 nominales ganadas; run_heavy8/8, pero random solo4/16 ante mejor referencia, no victoria general.

Ensamblado exacto: red ascendente32vectores30487bytes con1173 instrucciones vectoriales estáticas que referencian rsp; red16vectores9993bytes y125 referencias. Descendentes también archivadas. No contar rbp como pila sin probar que es framepointer: bajoO3 puede ser puntero de datos. Estos son conteos estáticos, no spills dinámicos medidos, DRAM ni explicación causal de todos los ciclos. La menor presión/tamaño es compatible con hipótesis, pero la nueva partición también cambia trabajo y profundidad. No se han contado hojas/particiones dinámicas.

Se encadena E041 registrada después de E040 y antes de nuevos datos: MISMO binario/DSOs, nuevos tamaños/semillas y recheck del problema separado. No recompilar ni elegir umbral ganador. Correctitud total E0406336 iniciales+21120 benchmark,ASan/UBSan6624 extra. Índice global221402 muestras/257996 salidas completas al cerrarE040; diagnóstico/sanitizadores aparte.


## E041 — holdout del MISMO binario, sin ajuste

`run_existing.py` verifica ejecutable, DSOs y snapshots antes/después; no compila ni cambia umbral. Conserva warmup, orden aleatorio, CPU2, región medida y comprobación exacta. Nuevos tamaños8209/180013/1500007, semillas14009/41011/58013,22 distribuciones,198 nominales (como máximo180 arrays distintos), once repeticiones y diez algoritmos.

Holdout:21780 muestras/23760 salidas exactas. Quick128 gana17/18 uniform/SplitMix, pero FALLA criterio estricto en180013/SplitMix/14009: control/candidato0.985329, host/candidato0.945620. Robustez FALLA en180013/few/58013:0.896836. Hay pérdidas grandes en algunos forced, aunque no fueran parte de ese criterio. Gana66/198 nominales ante mejor referencia. No retocar n/umbral ni quitar semillas.

Diagnóstico separado y preregistrado: n8193, semillas12007/33013, skew/uniform/dense16,51 repeticiones,3060 muestras/3120 salidas exactas. El problema original skew/33013 no se reproduce: ahora DSO/candidato1.121 y host/candidato1.109, frente a0.898/0.883 enE040. Ambos resultados permanecen. No más reintentos; no atribuir causa a allocator, ASLR, caché o frecuencia. Recompilar no era condición necesaria para cambiar el resultado, pero igualdad de bytes no implica direcciones/estado idénticos. El recheck no es holdout independiente ni rescata los criterios fallidos.

Balance E038–E041:96296 muestras y113472 salidas completas nuevas;15732 casos de sanitizadores y704 diagnósticos exactos aparte. Índice global246242 muestras/284876 salidas completas. No queda ningún proceso pendiente. Se avisó punto de compacción después de varias etapas encadenadas. E042 propuesta, aún sin ejecutar ni preregistrar: [[10 - Diagnosticar variabilidad antes de adaptar]].


## E042 — trabajo medido y fallos que no se reprodujeron

2026-11-05. [[E042 - Prerregistro trabajo y procesos]]. Los 216 resultados instrumentados O3 coinciden exactamente con std::sort y respetan guardas. E042-B conserva 29.760 muestras, 30.720 salidas exactas con calentamiento y mapas de 96/96 procesos. Mismo ejecutable y DSOs E040, verificados antes y después. Los fallos antiguos de skew, SplitMix y las tres forced no se reproducen en las ocho medianas por proceso. Few pierde en una mediana contra DSO256 por menos de1%. Se mantienen los negativos históricos y el carácter diagnóstico de la repetición. Ver [[13 - E042 trabajo y variación]].

El sanitizador inicial comprobó seis salidas triviales y se atascó al iniciar el segundo proceso vacío. Se detuvo con SIGTERM y se conserva stderr completo de2.050.409.610bytes con DEADLYSIGNAL repetido. La [[E042 - Adenda sanitizadores]] fijó un único contraste con host persistente noPIE, límite de archivo y timeout. Las mismas bibliotecas sanitizadas pasan 7.464 comprobaciones exactas con guardas en esa configuración, sin stderr. El origen del fallo inicial sigue sin aislarse.

La revisión de fuentes primarias [[11 - Literatura y límites de novedad]] encuentra antecedentes de distribución predictiva, redes SIMD y ordenación por frecuencia. [[12 - Síntesis del reto y candidatos]] reúne modelo, cotas, pseudocódigo, evidencia a10M de E030 y criterios para un eventual artículo. No hay novedad ni superioridad general demostradas.

## E043 — prueba de escala congelada

Se registra [[E043 - Prerregistro escala]] antes de nuevos tiempos. El mismo ejecutable E040 prueba100k/1M/10M con dos semillas y diez distribuciones, más100M en tres casos y siete algoritmos. Se mide RSS del proceso completo. E043 sigue al cierre de E042 sin compilación de rendimiento ni cargas intensivas simultáneas.

E043 completo. 3063 muestras y 3684 salidas exactas. A10M quick128 gana17/20 ante DSO256 y1/20 ante la mejor referencia incluida. En las cuatro uniform/SplitMix gana al DSO y pierde ante vqsort. A100M gana2/3 ante DSO256 y0/3 ante mejor referencia. Uniforme604,556ms, few167,699ms, forced_middle673,369ms. RSS máximo1148,9–1149,2MiB del proceso completo. [[15 - Escala y contadores]].

## E044 — contadores de la llamada exacta a las bibliotecas

La prueba externa `perf stat` devolvió los cuatro eventos genéricos en WSL. Se registró [[E044 - Prerregistro contadores]] antes de medir. Host independiente con generador exacto y las mismas DSOs E040. Sin compilación ni cargas concurrentes con E043. 176 llamadas medidas, 192 salidas exactas y 88 controles vacíos. Grupo activo al menos99% en todas las filas. Uniforme10M registra6,6% menos ciclos y11,1% menos fallos genéricos de caché, con0,14% más instrucciones y27,6% más fallos de rama. Esto caracteriza la llamada observada. La causa de las regresiones anteriores sigue abierta y no se infiere DRAM.

E042–E044 cerradas. El próximo contraste cambia solo el kernel de mezcla del árbol E038. [[14 - Diseño de mezcla SIMD]] contiene argumento de correctitud, tratamiento de colas y antecedente directo. Aún falta fijar matriz y escribir el prototipo. No quedan procesos del proyecto en ejecución entre turnos.

El usuario pide cambiar la prioridad de la búsqueda. Se revisan antecedentes de reparto por bloques y de posiciones con colisiones y se formula una hipótesis con presupuesto explícito. La dirección de una casilla codifica el prefijo de la primera clave, de modo que solo un residual necesita ordenación explícita. La combinación precisa tiene novedad sin verificar. [[16 - Orden implícito y presupuesto]] reúne la cuenta de ocupación, la prueba de exactitud y la condición de descarte. No se ejecutaron pruebas nuevas.

## Sesión de razonamiento, sin experimentos

El usuario pidió tiempo dedicado a mecanismos y fallos antes de pasar a práctica. La revisión cruza [[17 - Presupuesto de memoria]], [[18 - Multiconjunto y ambigüedad]] y [[19 - Rutas alternativas]]. A partir del coste de reinicios y accesos dispersos, [[20 - Diseño de celdas ordenadas]] acota una tabla por prefijo y guarda tres sufijos con contador y época. El residuo uniforme esperado a 10M baja a unas 62.149 claves. E007 impide convertir esa cifra en argumento suficiente de rapidez. Se encontraron antecedentes cercanos de sufijos, cubetas, marcas de reinicio y chunks.

La elección tras comparar mecanismos es [[21 - Decisión tras el análisis]]. La reparación dispersa tiene la predicción más fuerte. Certifica tramos que se mantienen por valor y escribe exactamente las D posiciones incorrectas. El caso de 20 swaps de E043 necesita como máximo 40 escrituras de claves. La bisección por extremos reduce las lecturas después de la primera pasada. La tabla local queda como candidata distinta para uniforme, con más riesgo de memoria y emisión. No hubo código de sorter nuevo, compilación, mediciones ni procesos de investigación pendientes.

El usuario aclara la prioridad de un sorter general para aleatoriedad de distintas distribuciones. La reparación dispersa pasa a vía secundaria. Se guarda [[22 - Relevo para un sorter general]] con la distinción entre exactitud universal, predicciones bajo uniformidad y robustez práctica en familias diversas. E044 sigue siendo la última etapa experimental.


## E045 — Hoja de tres sufijos, filtro fallido

Prerregistro antes de programar y medir. En dos uniformes preparados de 10M, las celdas completan 256 grupos con 61.844 y 62.086 claves residuales y tardan 94,78 y 94,38 ms frente a 37,18 y 37,68 ms del control copia + vqsort. El desbordamiento tardío obliga a leer las 10M claves del intento y ejecutar todo el respaldo. La hoja se descarta para el ranking completo. [[23 - E045 celdas descartadas]].

El primer proceso dense16 nativo cae con excepción de acceso. El binario exacto termina ese caso bajo GDB. La recuperación única del mismo binario completa 15/18 entradas combinadas y conserva 210 muestras y 240 salidas exactas, más 144 de correctitud inicial. Faltan un skew y ambos mixed, con el mismo código. Se conserva el diagnóstico separado de los tiempos. E046 sustituye las celdas por un certificado de cobertura y conteo exacto de multiplicidades. [[E046 - Prerregistro ventanas]].


## E046 — Ventanas con certificado, ganancia de mecanismo y fallo de robustez

En Ubuntu WSL, 50 salidas verificadas con guardas antes de medir. Después 420 muestras y 480 salidas exactas con calentamiento. El conteo supera a vqsort por 2,55–2,62× en dense16, 1,71–1,74× en skew y 2,01–2,08× en bimodal. El rechazo tardío lee las 10M posiciones, encuentra 1.250.001 externos y añade 2,20–2,76 ms. Uniforme, mixed y prefix_distinct van por bypass. [Filtro E046](../results/e046_windows_filter/summary.md).

El filtro falla en equal por 0,28 ms en ambas semillas y en few/62039 por 2,48 ms. En few la ruta es bypass y el código de vqsort usa estado de pivote mutable entre llamadas. Aún no se ha atribuido la diferencia a la trayectoria de pivotes. No se ejecuta full de E046. E047 cambia el certificado inicial por comprobación de bloques constantes y empareja estados iniciales de vqsort solo en el nuevo filtro. [[E047 - Prerregistro certificado por bloques]].


## E047 — Certificado por bloques y comparación completa

El certificado comprueba prefijos constantes en bloques de 32 y reutiliza la certeza para contar externos desde el primer bloque distinto. El filtro con dos semillas nuevas y estados emparejados de vqsort supera las condiciones fijadas. 54 salidas verificadas con guardas, 420 tiempos y 480 salidas exactas del filtro. El control de pivotes solo se activa en el filtro. [Tabla](../results/e047_windows_filter/summary.md).

El mismo binario, verificado por hash, completa 1M y 10M frente a vqsort, x86-simd-sort e IPS2Ra secuencial con su estado normal. 1.344 tiempos y 1.536 salidas exactas, incluidos calentamientos. Obtiene la menor mediana en 14/24 entradas en cada tamaño. A 10M, mejora sobre la mejor referencia 2,78–2,81× en dense16, 1,68–1,89× en skew y 1,92–2,08× en bimodal. Dos intercalaciones de las mismas ventanas también ganan en las cuatro entradas. Uniforme, mixed y prefix_distinct delegan. En el adversario añade 1,87–3,23 ms a vqsort. Pierde ambas equal de 10M por aproximadamente 13–17% frente a vqsort, además de few y casi ordenado frente a la mejor referencia. [Matriz y negativos](../results/e047_windows_full/summary.md).

Se guarda el argumento de exactitud, el límite auxiliar y el siguiente contraste de compactación de externos en [[24 - Ventanas y certificado]]. Índice completo 281.249 muestras y 321.776 salidas exactas con calentamientos. El parcial E045 y verificaciones previas con guardas quedan aparte. No hay procesos de SuperSort en ejecución.


## E048 — Compactación AVX2 con la misma cobertura

A 10M, la compactación gana 2,43–2,45× en las cuatro mezclas 50/50 aleatorias de una y dos ventanas. Una 50/50 periódica cae por debajo del límite (6,10 ms escalar, 7,71 ms AVX2). El filtro falla y la ruta de E047 sigue intacta. La clasificación escalar tarda unos 6 ms con alternancia y unos 29 ms con intercalación aleatoria de las mismas secuencias. El diagnóstico no identifica el coste físico. Se conservaron 252 tiempos, 288 salidas exactas con calentamientos y 2.248 verificaciones previas. [[25 - Compactación y separación in situ]].

E049 elimina el buffer de externos mediante dos salidas en el array original, con la misma ventana conocida y dos sorteos disjuntos. Prerregistro antes de implementar. [[E049 - Prerregistro separación in situ]].


## E049 — Separación hacia ambos extremos

Se elimina el buffer de externos y su copia de vuelta. La ventana se entrega preparada. Gana a vqsort 1,22–1,39× en agrupadas y periódicas 50/50, pero pierde ambas 50/50 aleatorias (37,88–38,58 ms frente a 36,67–36,85 ms). Un 95/5 queda por debajo del límite frente a escalar. 336 muestras, 384 salidas exactas y 4.916 verificaciones previas. El filtro falla. [[25 - Compactación y separación in situ]].

Se registra E050 antes de programar el cursor único. Elimina el segundo flujo de lectura y su coordinación, y paga el desplazamiento de los externos altos. Medir tres fases en modo separado. [[E050 - Prerregistro cursor y fases]].


## E050 — Un cursor, con fases separadas

La nueva ruta supera al split en 50/50 aleatoria pero queda en 1,025–1,034× frente a vqsort con ventana preparada, por debajo de 1,10. Pasan los demás límites. En el modo de fases, la clasificación aleatoria baja de 15,28 a 12,23 ms, el sort residual sube de 20,69 a 21,59 ms y la reconstrucción se mantiene alrededor de 1,5 ms. Se conservan 336 muestras y 384 salidas exactas, más 70 llamadas y 80 salidas en diagnóstico y 4.916 verificaciones previas. [[25 - Compactación y separación in situ]].

E051 contrasta coste fijo por clave con un histograma auxiliar de 256 contadores y un adversario con un externo repetido. No se cambia la política de E047. [[E051 - Prerregistro clasificación de coste fijo]].


## E051 — Clasificador de coste fijo

El ensamblado confirma que la clasificación no salta según la clave. En 50/50 aleatoria preparada gana 1,075–1,081× frente a vqsort, por debajo de 1,10. En 95/5 pierde en ambas semillas por 20–23% frente al escalar con buffer. El adversario repetido pasa. En el diagnóstico, la clasificación aleatoria baja a 10,40 ms y el sort residual queda en 21,72 ms. En periódica y 95/5 el coste fijo perjudica la clasificación. 392 muestras, 448 salidas exactas, 4.916 guardas y 64 salidas exactas del modo de fases. [[25 - Compactación y separación in situ]].

E047 sigue como candidato general medido. No se amplía el presupuesto de externos ni se promueven los caminos E048–E051. Se propone un contraste del sort residual con reparto grueso, cobrando el recorrido completo. Índice de tandas completas 282.565 muestras y 323.280 salidas exactas. No hay procesos pendientes.


## E052 — Objetivo de 25% y hojas de 16 bits

El usuario fija un mínimo de 25% de velocidad para el sorter general. La primera meta operativa es razón de tiempos ≥1,25 frente a la mejor de vqsort, x86-simd-sort e IPS2Ra por cada caso principal de 10M, en la misma tanda y con el coste completo. F5 queda como referencia especializada adicional por reproducir. [[26 - Meta del 25 por ciento y hojas compactas]].

El reparto con hojas compactas pierde en ambos residuales de 5M (35,92–36,13 ms frente a 23,24–23,58 ms) y en ambos uniformes de 10M (80,12–81,01 ms frente a 46,93–48,41 ms). Con el mismo reparto, wide/packed queda en 0,985–1,025 en uniforme 10M. Un analizador confundió claves con hojas. La recuperación verificó el mismo binario y ejecutó solo las 21 entradas pendientes. 408 comprobaciones previas, 546 tiempos y 624 salidas exactas. Se conserva la excepción inicial. [[E052 - Adenda telemetría]].

E053 aborda la baja cardinalidad dispersa mediante un diccionario comprobado y conteo, con el adversario de una clave desconocida tardía. [[E053 - Prerregistro diccionario por bits]].


## E053 — Diccionario exacto de baja cardinalidad

Con propuesta, pertenencia exacta, cuatro tablas y emisión, gana 1,54–1,67× frente a vqsort en las cuatro entradas few/few_permute de 10M. El adversario tardío examina las 10M claves y añade 3,35–4,67 ms. Un caso few_permute prefiere una sola tabla. Pasan las puertas prerregistradas. 270 comprobaciones previas, 378 tiempos y 432 salidas exactas. [[27 - Diccionario exacto para pocas claves]].

E054 paga el compuesto y compara en 10M con semillas nuevas ante E047, diccionario autónomo, vqsort, x86-simd-sort e IPS2Ra. [[E054 - Prerregistro compuesto con diccionario]].


## E054 — Cobertura del diccionario frente a tres referencias

El compuesto paga ambos probes cuando corresponde y conserva una sola certificación completa. Con estados habituales de pivotes, 786 comprobaciones previas, 1.260 muestras y 1.440 salidas exactas. En 10M, el diccionario dentro del compuesto gana 1,49–1,60× frente a la mejor de vqsort, x86-simd-sort e IPS2Ra en las cuatro few/few_permute. También pasan las seis dense16/skew/bimodal. Meta de 25% en 10/22 principales, meta general pendiente. [Matriz completa](../results/e054_combined_full/summary.md).

Uniforme, prefijos amplios y mixed delegan. Few_dominant elige ventana y tarda 13,16–13,29 ms, frente a 8,19–8,47 ms del diccionario autónomo. El adversario tardío paga 3,06–3,62 ms sobre vqsort. El contraste siguiente puede aislar la prioridad cuando las dos propuestas son válidas y la reutilización exacta del prefijo contado cuando falla una clave tardía. La ruta de alta entropía requiere su propio mecanismo y comparación. [[27 - Diccionario exacto para pocas claves]].

Acumulado del índice 284.749 muestras y 325.776 salidas exactas con calentamientos. No hay procesos en ejecución.

## E055 — Una lectura global con cubetas virtuales

**Demostrado.** Cada byte alto recibe como máximo `n` claves. El cursor final, incluida la cola parcial, da la longitud exacta. Recorrer las cubetas por byte y ordenarlas por sus 24 bits bajos preserva orden y multiplicidades. En la primera verificación se detectó que `scatter_nt` escribía la cola sin avanzar el cursor. La recuperación activa el avance para E055 y conserva el comportamiento de los llamadores anteriores. El intento original terminó antes de medir y también dejó al descubierto un error al escribir el informe de Python, corregido en la recuperación. [Fallo original](../results/e055_virtual_filter/verify.stderr.txt). [[E055 - Prerregistro cubetas virtuales]].

**Medido.** A 10M la variante virtual reduce la mediana frente al control contado en los ocho casos. El cociente contado/virtual es 1,047–1,056 en uniforme, 1,063–1,080 en prefijos amplios, 1,023–1,105 en mezcla y 1,157–1,186 en `dense16`. La razón vqsort/virtual queda en 0,751–0,778, 0,526–0,535 y 0,492–0,541 en las tres familias prioritarias. Falla 1,25× en las seis entradas y el mínimo de 1,05× sobre el control en una uniforme. `dense16` registra 0,556–0,568 frente a vqsort. Se descarta esta implementación sin ampliar. 168 muestras, 192 salidas exactas con calentamientos y 153 comprobaciones previas, incluido el rechazo síncrono de reserva. La comparación conjunta incluye el cambio de reserva y distribución virtual de páginas. No hay tiempos por fase ni medición de RSS. [Matriz y datos](../results/e055_virtual_filter_recovery/summary.md).

**Pendiente.** Aislar la mezcla 50/50 con dos particiones binarias SIMD in situ en los límites de una ventana propuesta. Mantener los dos vqsort de los extremos y la emisión de E049. El cambio separa las escrituras de partición de las actualizaciones del histograma, con una segunda partición parcial y una lectura adicional de los internos. Medir desde el probe compartido, con un control concentrado fuera de la ventana. Exigir 1,25× frente a vqsort en las dos semillas y mejora frente a E049 con la misma propuesta. E054 conserva 10/22 como última matriz del compuesto. Acumulado del índice 284.917 muestras y 325.968 salidas exactas. No hay procesos en ejecución.

## E056 — Dos particiones binarias para la mezcla

**Demostrado.** El corte alto deja un prefijo con todas y solo las claves hasta el límite alto. Cortar ese prefijo por debajo de la base delimita la ventana exacta. Ordenar ambos extremos y emitir las multiplicidades del centro conserva todo el multiconjunto incluso cuando el probe sobrestima la ventana. Las comparaciones de borde cubren cero y `UINT32_MAX`. [[E056 - Prerregistro dos particiones]].

**Medido en el filtro.** Con el mismo probe, reservas y finalizador, la ruta binaria gana 1,150× y 1,244× frente a E049 en `mixed`. Frente a vqsort directo da 1,251× y 1,261×. En `dense16` paga 17,28–19,12 ms frente a 12,38–12,91 ms de E049. La propuesta engañosa da 0,917–0,919× frente a vqsort y termina con los 256 internos correctos. Uniforme y prefijos amplios delegan en vqsort. 210 muestras, 240 salidas exactas con calentamientos y 3.243 comprobaciones previas. [Filtro](../results/e056_binary_filter/summary.md).

**Pendiente tras el filtro.** La puerta pasa y autoriza repetir con las tres referencias, dos semillas originales y dos adicionales para `mixed`. Los márgenes del filtro son de 0,0014× y 0,0110× sobre la meta. [[E056 - Adenda confirmación]].

**Medido en la confirmación.** La variante mejora a E049 en las cuatro mezclas por 1,180–1,275×. Vqsort vuelve a ser la mejor externa en las cuatro. Las razones de vqsort sobre la variante son 1,196×, 1,275×, 1,228× y 1,239× en orden de semillas 42701, 91009, 53309 y 78041. Solo 91009 pasa 1,25×. A las otras les faltan 1,375, 0,605 y 0,282 ms, respectivamente, para el presupuesto de su propia tanda. En 42701 la variante también reduce su mediana respecto al filtro, pero la referencia baja de 43,412 a 38,008 ms y el cociente cae. Son observaciones entre tandas y no aíslan la causa de la variación. En `dense16` la variante pierde frente a E049 y en `late_miss` da 0,906–0,923× frente a vqsort. Uniforme y prefijos amplios delegan. 420 muestras, 480 salidas exactas con calentamientos y 3.293 comprobaciones previas. [Confirmación](../results/e056_binary_full/summary.md).

**Pendiente.** Probar solo el cambio del segundo corte. Conservar el corte alto de E056. En el prefijo restante, `compact_window_forward` de E050 puede contar internos y escribir las claves inferiores con un cursor adelantado en la misma lectura. Elimina la relectura del centro y las escrituras necesarias para colocarlo antes de contarlo. Paga máscaras, enumeración de internos y stores de compactación en ese prefijo. Muchas claves inferiores y pocas internas son el adversario de esta fusión. Mantener la detección, la reserva, los vqsort de los extremos y la emisión de E056. Comparar contra E056 y vqsort directo. Exigir mejora en ambas semillas originales y 1,25× frente a vqsort en ambas antes de ampliar. La confirmación de E056 incumple la puerta y se aplaza su integración. E054 sigue en 10/22. Acumulado del índice 285.547 muestras y 326.688 salidas exactas. No hay procesos en ejecución.

## E057 — Unión encadenada en caché

**Demostrado.** Dos productores de uniones binarias pueden entregar sus resultados por bloques consecutivos a un consumidor. Cada uno conserva su estado de unión y vuelve a llenar su bloque cuando se agota. El consumidor ve las mismas dos secuencias ordenadas que en el control materializado. En ambos brazos se ordenan los mismos tramos con vqsort, se usa la misma unión AVX2 binaria y se alternan los mismos destinos por nivel. En 10M el espacio reservado para los intermedios pasa de 40 MB a 16 KiB, además del buffer común de destino. La primera verificación cubre tramos vacíos, desiguales, colas, duplicados, extremos y guardas. [[E057 - Prerregistro unión en caché]].

**Medido.** Encadenar gana 1,170–1,210× frente a materializar en las ocho entradas y ahorra 15,53–17,36 ms por mediana. En uniforme queda en 88,93–91,36 ms frente a 45,98–48,06 ms de vqsort. En prefijos amplios queda en 82,72–83,53 ms frente a 45,60–46,03 ms. También pierde frente a vqsort en mezcla y `dense16`. Falla la puerta en las cuatro entradas principales y se cierra esta implementación. 168 muestras, 192 salidas exactas con calentamientos y 1.320 comprobaciones previas. El contraste cambia la reserva y la frecuencia de recarga. Los tiempos no separan fases ni identifican tráfico físico. [Matriz y muestras](../results/e057_stream_merge/summary.md).

**Pendiente.** Origami es el antecedente de la idea y queda pendiente de un contraste directo. Su entrada pública completa está preparada para MSVC/Windows y geometría de potencias de dos. Medirla a 10M con el contrato del proyecto requiere adaptar colas, reserva, liberación y copia de vuelta. Se probó un kernel propio con topología binaria de dos niveles, así que el resultado tiene ese alcance. El siguiente contraste puede cambiar de mecanismo y medir qué parte del tiempo de vqsort se dedica a pares de particiones independientes. Si ese tramo deja presupuesto para recuperar alrededor de 10 ms, probar procesar bloques de las dos particiones alternadamente con los mismos pivotes y escrituras. Conservar en cola la fusión de dos niveles en cuatro salidas, ordenar grupos pequeños en paralelo por carril y ordenar posiciones mediante máscaras. Acumulado del índice 285.715 muestras y 326.880 salidas exactas. No hay procesos en ejecución. [Artículo de Origami](https://www.vldb.org/pvldb/vol15/p259-arman.pdf), [implementación pública](https://github.com/arif-arman/origami-sort/commit/a1edd5dd6affd754b2ed99faa48d93966b9af34c).

## E058 — Presupuesto de pares de particiones de vqsort

**Medido.** En las cuatro entradas de 10M, vqsort limpio tarda 45,71–46,23 ms. Los dos miembros de cada par de particiones hermanas acumulan 30,65–31,46 ms bajo traza. La suma de la llamada corta de cada par queda en 13,41–13,87 ms brutos y 12,39–12,85 ms tras descontar la lectura calibrada del reloj. El presupuesto necesario es 9,14–9,25 ms. Si se cuentan solo pares con ambos hijos de 1.024 claves o más, el techo bruto baja a 9,69–10,15 ms. Los dos niveles superiores completos cuestan 5,03–5,47 ms bajo traza. La traza añade 4,66–5,11 ms al total. Sus cifras incluyen prólogos y colas, y el modelo de solapamiento ignora el coste de mantener dos estados. Los procesos son independientes por muestra. La ronda previa se excluye y se verifica, y cada medición sigue siendo la primera ordenación de su proceso. Se igualó el estado inicial de los pivotes entre binarios y la elección de cortes también depende de la alineación del array. 56 tiempos y 64 salidas exactas. [Matriz y muestras](../results/e058_vq_pairs/summary.md).

**Decisión.** Las cuatro entradas dejan margen bajo el modelo ideal. E059 mide serie y alternancia con los mismos cortes y movimientos y vqsort directo como referencia. El margen de E058 es una estimación, sin una mejora observada frente a vqsort. Acumulado del índice 285.771 tiempos y 326.944 salidas exactas. [[E058 - Prerregistro pares de vqsort]]. [[E059 - Prerregistro alternancia de bloques]].

## E059 — Alternancia de bloques de particiones hermanas

**Demostrado.** Los dos brazos reutilizan la preparación de vqsort para obtener ambos pivotes antes de procesar la pareja. El control completa un tramo y después el otro. La variante avanza un bloque de cuatro vectores de cada tramo y termina las colas en serie. El orden de lecturas y escrituras dentro de cada tramo se conserva. Las comprobaciones previas comparan cortes, contenido y guardas de los dos brazos contra `Partition` de Highway en tramos desiguales, colas, duplicados y pivotes extremos, y también los sorters completos contra `std::sort`. Hay dos espacios fijos de trabajo en pila. La preparación anticipada del hijo derecho cambia el orden de consumo del generador frente a vqsort directo. Los dos brazos propios comparten ese cambio. [[E059 - Prerregistro alternancia de bloques]].

**Medido.** La alternancia ahorra 2,44–3,20 ms frente a la serie en las cuatro medianas de uniforme y prefijos amplios y gana 26/28 rondas pareadas. El control en serie tarda 49,66–50,31 ms, frente a 46,39–46,81 ms de vqsort directo. La alternancia termina en 46,61–47,86 ms, con razones vqsort/alternancia de 0,989 y 1,004 en uniforme y 0,971 y 0,989 en prefijos amplios. Aún faltan 9,19–10,69 ms en esas cuatro entradas. En `equal`, la preparación termina sin entrar en el bucle de parejas y el brazo alternado da medianas de 1,61–1,87 ms frente a 1,53–1,67 ms del control. La diferencia entre el control y vqsort directo combina cambios de planificación y del kernel. 126 muestras, 144 salidas exactas contando calentamientos y 1.590 comprobaciones previas. [Matriz y muestras](../results/e059_pair_schedule/summary.md).

**Decisión y siguiente contraste.** La alternancia reduce el coste dentro del prototipo y queda por debajo de 1,25× frente a vqsort en las cuatro entradas prioritarias. Se cierra y se mantiene E054 como candidato compuesto. Medir una clasificación de cuatro rangos repetida en varios niveles contra dos niveles de cortes binarios con los mismos tres pivotes y el mismo finalizador. E058 sitúa la raíz y sus dos cortes hijos en 5,03–5,47 ms incluso bajo traza, de modo que conviene cubrir más de dos niveles. Colocar los rangos externos en el array y copiar solo los centrales desde un auxiliar podría ahorrar una clasificación completa y parte de los movimientos. El caso que concentra casi todas las claves en el centro pierde el ahorro de copia. Las cuatro compactaciones, reserva, copia y respaldo entran en la cuenta. Acumulado del índice 285.897 muestras y 327.088 salidas exactas. No hay procesos en ejecución. [Presupuesto E058](../results/e058_vq_pairs/summary.md).

## E060 — Cuatro rangos en una pasada

**Demostrado.** Guardar un vector de cada extremo deja dos huecos cuyo espacio total crece con las claves enviadas al auxiliar. Cargar del lado del hueco menor garantiza espacio para ambos stores anchos. Los dos cursores centrales del auxiliar conservan al menos 16 posiciones entre sí y las colas se emiten con escrituras exactas antes de copiar al hueco central. El control ejecuta la partición binaria de Highway con los mismos cortes, y ambos árboles usan hasta seis dígitos con umbral de 32.768 y el mismo finalizador vqsort. Las comprobaciones previas cubren pertenencia a rango, contenido, guardas y reserva fallida antes de mutar el array. [[E060 - Prerregistro cuatro rangos]].

**Medido.** En uniforme la variante clasifica 50M frente a 100M claves acumuladas y copia 25M centrales, para unas 75M colocaciones lógicas frente a 100M. Aun así tarda 89,34–92,80 ms frente a 47,21–49,39 ms del control y 47,00–50,69 ms de vqsort. En prefijos amplios tarda 64,20–65,14 ms frente a 53,89–55,58 ms del control y 46,67–47,23 ms de vqsort. Copia 7,5M de 25M clasificadas. En `center` copia las 10M de la raíz y unas 30M en el árbol, con 97,44–102,38 ms de tiempo total. En `equal` copia todas las claves antes del respaldo, con 25,92–25,97 ms frente a 1,96–2,01 ms de vqsort. La contabilidad lógica desconoce el ancho físico de los stores. El tiempo incluye compactaciones, reserva, copia y ordenaciones finales que pueden recibir permutaciones distintas. 168 muestras, 192 salidas exactas con calentamientos y 4.944 comprobaciones previas. [Matriz y muestras](../results/e060_four_ranges/summary.md).

**Decisión.** La implementación pierde en las ocho entradas frente a ambos brazos y falla el filtro. Acumulado del índice 286.065 muestras y 327.280 salidas exactas. No hay procesos en ejecución.

**Selección del contraste de hojas.** De las 28 trazas medidas de E058 se cuentan como posibles hojas los hijos de una partición normal con longitud entre 1 y 128. El recuento deduce tamaños de los cortes, así que puede incluir hijos saltados por una ruta especial. Las cifras son medianas por entrada y los porcentajes se refieren a las 10M claves de cada ordenación.

| Familia | Semilla | Tramos ≤32 | Claves en tramos ≤32 | Pares con ambos ≤32 | Claves en tramos 65–128 |
|---|---:|---:|---:|---:|---:|
| uniform | 42701 | 7 | 200 | 0 | 93,27% |
| uniform | 91009 | 6 | 183 | 0 | 93,34% |
| prefix_distinct | 42701 | 7 | 211 | 0 | 93,32% |
| prefix_distinct | 91009 | 5 | 152 | 0 | 93,33% |

Un lote limitado a hojas de hasta 32 alcanza muy pocas claves. La franja de 65–128 es la que vale medir dentro de la ordenación completa. E035 cronometró redes de x86-simd-sort aisladas y sirve como antecedente del efecto del tamaño. Para decidir, separar el tiempo de las hojas de vqsort del muestreo de pivotes, comparar con una ejecución limpia y contrastar el techo de la franja pertinente con el ahorro requerido. Si ese techo queda corto, avanzar a posiciones con mapas de bits. [Cálculo reproducible](../analyze_e058_leaf_sizes.py), [trazas E058](../results/e058_vq_pairs/summary.md), [microbenchmark E035](../results/e035_leaves_linux/diagnostic-summary.md).

## E061 — Presupuesto de hojas de vqsort

**Medido.** Con ambos brazos alineados a 64 B, vqsort limpio tarda 45,04–46,86 ms en 10M, uniforme y prefijos amplios. Se cuentan todas las hojas terminales y se cronometra aproximadamente una de cada 16, con unas 6.374–6.497 medidas por ronda de 65–128. Por mediana, todas las claves pasan por hojas. El coste bruto estimado de todas las hojas es 11,35–11,56 ms y el corregido es 9,08–9,29 ms. La calibración da 20 ns. La franja 65–128 consume 8,46–8,65 ms corregidos y 33–64 consume 0,62–0,63 ms. En la franja de hasta 32 quedan rondas con hojas sin observación de reloj y su tiempo no entra en el estimador de esas rondas. El tiempo total con traza queda entre −0,86 y +0,47 ms frente al limpio por mediana. La estimación no incluye preparar pivotes. 56 tiempos completos, 112 salidas exactas contando el calentamiento de cada proceso. [Matriz y muestras](../results/e061_leaf_budget/summary.md).

**Decisión.** Suprimir todo el coste estimado de 65–128 ya queda corto en las cuatro entradas. Compartir el coste de una hoja entre ocho da un ahorro ideal de 7,40–7,57 ms, con preparación y emisión gratuitas, frente a los 9,01–9,37 ms requeridos. Se cierra la agrupación directa en ese árbol. Un diseño que cambiase el árbol tendría que incluir en el contraste el nuevo trabajo de partición. Acumulado del índice 286.121 tiempos y 327.392 salidas exactas. [[E061 - Prerregistro presupuesto de hojas]].

**Siguiente contraste.** El recuento de E058 suma el tiempo de `Partition` normal hasta cada umbral, restando a cada llamada la mediana del reloj. A 256 da 2,66–2,72 ms, a 512 da 4,82–4,90 ms, a 1.024 da 6,66–6,78 ms y a 2.048 da 8,39–8,54 ms. Son cifras de otra tanda y excluyen preparación de pivotes y hojas. Sirven para escoger un alcance, con un contraste sobre subárboles reales necesario para cuantificar el ahorro. Los mapas por posición mantienen un bit por aparición y abarcan la partición de subárboles además de sus hojas. E007 ya probó presencia por valor, E045 celdas por prefijo y E053 un diccionario para pocas claves. Comparar con vqsort sobre los mismos tramos y cobrar formar planos, localizar posiciones, reserva, emisión y copia de vuelta. Fijar un adversario con prefijo que se rompe por un extremo y otro con duplicados. No hay procesos en ejecución. [Cálculo reproducible](../analyze_e058_subtree_budget.py), [trazas E058](../results/e058_vq_pairs/summary.md).

## E062 — Mapas de bits por posición

**Demostrado.** Un bit por posición conserva cada aparición de cada valor. Tras quitar los bits constantes, recorrer cero antes que uno por los ocho planos superiores produce grupos ordenados entre sí. La ordenación por clave completa dentro de cada grupo resuelve los bits restantes. Los grupos de hasta cuatro usan inserción y los mayores al agotar planos usan vqsort. Se mantiene intacto el origen hasta emitir el tramo completo y copiarlo de vuelta. 4.168 comprobaciones previas, incluidos pocos bits bajos variables, un extremo que rompe un prefijo, duplicados, colas y guardas. [[E062 - Prerregistro mapas por posición]].

**Medido.** Se capturan los subárboles máximos de hasta 512 antes de elegir sus pivotes. Replay y bitmap reciben los mismos tramos, desplazamientos y estado inicial por tramo. Las cuatro medianas cubren 10M claves en 28.442–28.461 tramos. Vqsort sobre esos tramos tarda 18,01–18,78 ms y los mapas 104,15–105,35 ms. La mediana de la pérdida pareada es 85,72–86,73 ms. Se necesitaban 9,14–9,54 ms de ahorro, calculados con vqsort completo, que tarda 45,70–47,72 ms. La repetición cambia el contexto de caché del árbol vivo y los tiempos de la variante agrupan detección, planos, recorrido, residual y copia. El filtro cierra la implementación. 84 tiempos, 96 salidas exactas de los brazos contando calentamientos y 32 capturas exactas. Acumulado del índice 286.205 tiempos y 327.520 salidas comprobadas. [Matriz y datos](../results/e062_position_bitmap/summary.md).

**Siguiente contraste.** La partición normal sigue siendo un objetivo con presupuesto suficiente. Probar intercambiar solo las posiciones mal colocadas en una partición binaria de Hoare. Cada vector modificado se vuelca al completar su máscara, y los vectores correctos se omiten. Paga permutaciones, dos vectores activos y una cola exacta. E059 conservaba los stores, E060 cambiaba el número de destinos y E049 trataba una ventana y su histograma. Capturar tramos y pivotes para comparar el kernel de Highway y el de intercambio en las mismas entradas. Verificar corte, pertenencia, multiconjunto y guardas en colas y casos equilibrados, sesgados y ya separados. Registrar las escrituras solicitadas sin atribuir bytes a DRAM. El orden dentro de cada lado puede variar y cambiar el trabajo del sorter posterior. Exigir margen de unos 9–10 ms antes de medir el sorter completo. No hay procesos en ejecución. [Presupuesto E058](../results/e058_vq_pairs/summary.md).

## E063 — Partición binaria por intercambio de posiciones

**Demostrado.** Las dos máscaras de fallos identifican posiciones con claves del lado opuesto. Intercambiar el mismo número en los dos vectores conserva el multiconjunto y retira al menos una máscara. Los bloques correctos se omiten, cada bloque completo modificado se vuelca al terminar y el centro de hasta 15 claves se resuelve con una cola exacta. Las 8.224 comprobaciones previas incluyen todas las longitudes de 0 a 513, diferentes alineaciones, guardas, duplicados, extremos y cortes sesgados. [[E063 - Prerregistro intercambio de bloques]].

**Medido.** En uniforme y prefijos amplios se capturan 458 tramos por entrada, unos 22,17–24,39M de claves acumuladas. La mediana del control por lotes es 5,46–5,74 ms y la de intercambio 12,13–15,13 ms. Las escrituras ponderadas bajan de 329,33–329,77M a 167,44–168,59M posiciones de 32 bits. Highway cuenta los stores anchos y el intercambio también incluye su cola. El modelo mide solicitudes de escritura. Al ponderar la diferencia de tiempo por tamaño de clase, la pérdida proyectada es 78,34–85,72 ms, frente a 9,03–9,20 ms de ahorro requerido por el vqsort completo de esa tanda. Esta proyección parte de tramos preparados y una sola captura por entrada, con un tramo por clase grande. Los tiempos crudos de los lotes también pierden en las cuatro entradas. [Matriz y muestras](../results/e063_exchange_partition/summary.md).

En `skew95` las escrituras pasan de unos 20M a 3,70M y el intercambio pierde 2,06–2,35 ms de mediana pareada. En `separated` el intercambio pide cero escrituras y gana 1,00–1,23 ms. Se cierra la implementación en el filtro. 1.036 tiempos, 29.376 particiones exactas con calentamientos, 32 salidas completas de vqsort y 4 capturas exactas, más 1.836 particiones exactas en la pasada de telemetría. Los tiempos por lotes se contabilizan aparte en el índice. [Matriz y muestras](../results/e063_exchange_partition/summary.md).

**Siguiente contraste.** Medir el margen de un reparto grueso con finalizador vqsort de 32 bits. Capturar la frontera de subárboles de hasta 32.768 y medir el coste de finalizarlos tanto en el árbol como al repetirlos. Cobrar una copia secuencial de la disposición preparada al array en el brazo optimista. La diferencia entre el tiempo objetivo y ese brazo es el presupuesto para un reparto real. El diagnóstico separa esa decisión del coste de construir otro kernel y cambia el contexto de caché de los finalizadores. No hay procesos en ejecución.

## E064 — Presupuesto de un reparto grueso

**Medido.** Una frontera natural de 444–448 tramos de hasta 32.768 cubre las 10M claves. Se verifica la misma frontera y el estado inicial de pivotes. Dentro del árbol consume 28,14–28,74 ms y al repetirla desde la disposición preparada consume 29,30–29,82 ms. La diferencia pareada es 0,61–1,44 ms. Cobrar una copia secuencial de 40 MB y finalizar eleva el total a 32,52–33,25 ms. Frente a la meta de 36,61–36,86 ms, deja 3,61–4,24 ms de presupuesto. Las diferencias incluyen el contexto de caché. 112 tiempos, 128 salidas exactas de los brazos con calentamientos y 32 capturas exactas. [Matriz y muestras](../results/e064_distribution_budget/summary.md).

**Decisión.** El margen exige comprobar el coste de la segunda materialización antes de programar una arena de paquetes. Una arena de tamaño completo añade 80 MB lógicos de lectura y escritura antes de la copia ya cobrada, más clasificación y directorio. E065 mide la doble copia secuencial con auxiliar nuevo y finalizador idéntico. Acumulado de la tabla 286.317 tiempos y 327.680 salidas comprobadas. [[E064 - Prerregistro presupuesto de reparto]]. [[E065 - Prerregistro doble materialización]].

## E065 — Doble materialización con auxiliar nuevo

**Medido.** Al repetir la matriz de E064, vqsort completo tarda 45,45–46,93 ms. La copia preparada y el finalizador tardan 32,60–33,46 ms. Reservar un auxiliar nuevo de 40 MB, copiar primero a ese auxiliar y después al array, finalizar y liberar tarda 60,68–62,29 ms. La diferencia pareada es 28,20–28,86 ms. Agrupa reserva, primer acceso, copia adicional, liberación y el efecto de caché de la secuencia. Las mediciones no separan el coste de cada componente. Las cuatro entradas exceden su objetivo por 24,04–24,82 ms antes de elegir o clasificar rangos. La frontera cubre las 10M claves con 444–448 tramos por mediana. 140 muestras, 160 salidas exactas de los brazos contando calentamientos y 32 capturas exactas. Cero respaldos de reserva. [Matriz y muestras](../results/e065_staging_budget/summary.md).

**Decisión.** Cerrar el reparto grueso con auxiliar de tamaño completo y dos materializaciones separadas en este esquema. El próximo contraste es un reparto por bloques dentro del array, con finalizador vqsort por rangos. En E064 el presupuesto de un reparto que evite la copia global es 6,81–7,31 ms sobre los mismos tramos preparados. La permutación por bloques vendorizada en IPS2Ra es un punto de partida para medir ese coste sin asumir los tiempos del sorter completo. Elegir límites comparables en uniforme y prefijos amplios, cobrar selección y márgenes, y medir también una cubeta dominante. Acumulado de la tabla 286.457 tiempos y 327.872 salidas comprobadas. No hay procesos en ejecución. [[E065 - Prerregistro doble materialización]].

## E066 — Reparto in situ por bloques y vqsort por rango

**Demostrado.** Se usa la permutación por bloques y la limpieza de IPS2Ra con buffers de 512 B por destino. La limpieza deja todas las claves en su rango, y vqsort termina cada uno en el array original. Los nueve bits altos o la tabla monótona de prefijos ordenan los rangos entre sí. La versión adaptativa escoge cortes por cuantiles y colapsa los repetidos. La reserva fallida delega con la entrada intacta. 170 comprobaciones previas de pertenencia, multiconjunto, guardas, tamaños frontera y respaldo. [[E066 - Prerregistro reparto in situ por bloques]].

**Medido.** En uniforme ambos brazos usan 512 rangos y el adaptativo tarda 56,35–59,12 ms frente a 49,00–51,33 ms del fijo y 48,92–51,52 ms de vqsort. En prefijos amplios, el fijo deja ocho rangos y un tramo mayor de unos 1,25M. El adaptativo crea 512 y baja el tramo mayor a 29.299–39.061 claves. Mejora frente al fijo por 1,123–1,237×, pero queda en 53,92–54,43 ms frente a 48,44–51,87 ms de vqsort. En las cuatro entradas, la elección y reparto adaptativos cuestan 22,93–26,86 ms y la finalización 30,65–32,12 ms. En `dominant`, un tramo de 9,51M hace que el reparto se añada a un finalizador todavía grande. `dense16` activa el respaldo de muestra a un coste de 0,75–0,78 ms. 168 muestras y 192 salidas exactas contando calentamientos. [Matriz y fases](../results/e066_inplace_blocks/summary.md).

**Decisión.** El adaptativo falla la meta en las cuatro entradas y se cierra como candidato. Antes de reemplazar una parte del reparto, E067 mide clasificación, permutación, márgenes y resto de preparación por separado. Acumulado del índice 286.625 tiempos y 328.064 salidas exactas. [[E067 - Prerregistro fases de bloques]].

## E067 — Presupuesto por fase del reparto por bloques

**Medido.** Las cuatro entradas prioritarias repiten los brazos E066. Clasificación y llenado de buffers en el adaptativo cuestan 13,32–17,24 ms, permutación 6,78–7,66 ms, limpieza de márgenes 0,027–0,029 ms y el resto 0,72–0,79 ms. El adaptativo da 51,67–55,86 ms frente a 48,44–49,50 ms de vqsort. En el fijo, clasificar uniforme cuesta 9,46–9,93 ms incluso con el extractor directo, y permutar 7,11–7,42 ms. La variación de medianas frente a E066 incluye diferencias de tanda y de instrumentación. 84 muestras, 96 salidas exactas contando calentamientos y 170 comprobaciones previas. [Matriz y datos](../results/e067_block_phases/summary.md).

**Decisión.** Al restar toda la clasificación del adaptativo, `prefix_distinct/42701` queda en 40,47 ms frente a 38,75 ms de objetivo. Las otras tres dejan solo 0,54–1,53 ms para un sustituto. Permutación, márgenes y resto fallan como objetivos aislados en las cuatro. Este modelo conserva fijos el orden interno, el trabajo de las otras fases y la finalización. Se cierra la optimización de una sola fase para este diseño. Acumulado del índice 286.709 tiempos y 328.160 salidas exactas. [[E067 - Prerregistro fases de bloques]].

**Siguiente contraste.** Medir un reparto por ciclos que combine colocar la clave y materializar su posición de salida en un solo movimiento. Con los límites exactos de las cubetas, el ciclo lleva cada clave al siguiente hueco incorrecto de su rango y omite posiciones correctas. Esto evita llenar primero bloques homogéneos para volver a permutarlos, a cambio de una lectura de histograma y accesos dispersos y dependientes. El filtro preparado mide ese coste con los mismos cortes y finalizador de E066, y un filtro completo cobraría elección, histograma, reserva y respaldo. El alcance es el coste, con repartos cíclicos previos como antecedente. No hay procesos en ejecución. [[17 - Presupuesto de memoria]].

## E068 — Reparto por ciclos con límites preparados

**Demostrado.** Los cursores saltan las claves ya correctas. Cada hueco incorrecto recibe una clave de su rango y libera la que estaba allí. El ciclo se cierra al recuperar una clave del rango de partida. Los límites exactos garantizan la existencia de un hueco mientras quede una clave entrante. La telemetría confirma una escritura lógica por posición inicialmente incorrecta y cero para el control agrupado. Las 7.830 comprobaciones previas cubren guardas, rangos vacíos, duplicados, extremos, colas y una sola cubeta. [[E068 - Prerregistro reparto por ciclos]].

**Medido.** En uniforme el reparto por ciclos cuesta 95,24–100,71 ms frente a 24,39–25,85 ms de bloques. En prefijos amplios cuesta 62,73–62,76 ms frente a 21,60–21,83 ms de bloques. Los ciclos escriben alrededor de 9,98M posiciones. El total de ciclos es 124,86–133,07 ms en uniforme y 93,38–94,93 ms en prefijos amplios, con la misma geometría y el mismo finalizador que bloques. Se exige la meta frente a vqsort y mejora frente a bloques. Falla en las cuatro entradas incluso con elección e histograma preparados. En `dominant` mejora frente a bloques por 1,234–1,264× y pierde frente a vqsort. En `grouped` usa el mismo multiconjunto que uniforme, solicita cero escrituras y registra 1,455–1,472× frente a vqsort, todavía con preparación fuera del reloj. El orden dentro de rangos puede cambiar entre brazos y las escrituras lógicas no miden tráfico físico. 168 tiempos, 192 salidas exactas contando calentamientos y ocho pasadas exactas de telemetría. [Matriz y muestras](../results/e068_cycle_partition/summary.md).

**Decisión.** Se cierra la ruta general de ciclos. El siguiente contraste conserva el árbol superior y cambia solo la finalización de los tramos naturales de E064. Un mínimo y máximo exactos permiten verificar si cabe una clave relativa de 24 bits, incluso si el tramo cruza un prefijo fijo. Probar dos pasadas radix locales y reutilizar un scratch acotado. Un tramo más ancho o un extremo aislado paga la detección y delega. Cobrar detección, scratch, materialización y respaldo y exigir un ahorro del 20% del tiempo de vqsort completo en las cuatro entradas. Esta tanda aislaría el finalizador donde E055 mezcló el reparto global y los dos dígitos locales. F5 queda como referencia adicional, y el sitio del proyecto indica que su código se obtiene del autor. Acumulado del índice 286.877 tiempos y 328.352 salidas exactas. No hay procesos en ejecución. [Frontera E064](../results/e064_distribution_budget/summary.md), [página de IRL](https://irl.cs.tamu.edu/projects/streams/).

## E069 — Radix local de 24 bits

**Medido.** Mínimo y máximo exactos permiten usar dos dígitos de hasta 12 bits relativos a la base. El candidato acepta las 10M claves uniformes y alrededor de 9,93M en prefijos amplios. Usa un scratch reutilizable de 128 KiB y dos histogramas de hasta 16 KiB cada uno. Frente a los mismos tramos con vqsort, ahorra 1,72–1,88 ms en uniforme y pierde 9,77–10,17 ms en prefijos amplios. Necesitaba ahorrar 9,27–9,53 ms. La escasa fracción de respaldo en prefijos amplios acota su alcance, y la tanda no separa el coste de cada reparto. 84 tiempos, 96 salidas exactas contando calentamientos, 32 capturas exactas y 4.806 comprobaciones previas. Se cierra el kernel 12+12. E070 quita el segundo reparto con sufijos de 16 bits por grupo. [[E069 - Prerregistro radix local de 24 bits]]. [Matriz](../results/e069_radix24/summary.md).

## E070 — Sufijos locales de 16 bits

**Medido.** Un reparto por el byte alto del desplazamiento deposita sufijos de 16 bits en 64 KiB de scratch. Vqsort ordena cada grupo y se expande directamente al array. Con la misma frontera, pierde 4,09–4,27 ms frente a `replay` en uniforme y 51,30–52,64 ms en prefijos amplios. La cobertura es completa en uniforme y del 99,3% en prefijos amplios. El experimento agrupa histograma, reparto, sort de sufijos y expansión. Falla en las cuatro entradas y se cierra el kernel. 84 tiempos, 96 salidas exactas contando calentamientos, 32 capturas exactas y 4.806 comprobaciones previas. E071 cambia de mecanismo y prueba quitar el muestreo conservando la partición SIMD. [[E070 - Prerregistro sufijos locales de 16 bits]]. [Matriz](../results/e070_suffix16/summary.md).

## E071 — Pivote aritmético local

**Medido.** Calcular mínimo y máximo iniciales y propagar límites permite reemplazar la elección de pivotes por el punto medio. Usa la misma partición SIMD y hoja de Highway. Si un lado cae por debajo de `n/8`, se paga la partición y el tramo se termina con vqsort. Los cuatro casos entran en el candidato en todos los tramos por mediana. La telemetría no separa los respaldos internos. El ahorro pareado es 4,38–4,49 ms en uniforme y 5,02–5,13 ms en prefijos amplios, frente a 9,37–9,47 ms requeridos. Es el mayor ahorro local de E069–E071. Incluye quitar el muestreo y cambiar el árbol inferior. Falla la puerta en las cuatro entradas. 84 tiempos, 96 salidas exactas contando calentamientos, 32 capturas exactas y 4.806 comprobaciones previas. E072 contrasta una geometría de radix con hasta 256 destinos por pasada. [[E071 - Prerregistro pivote aritmético local]]. [Matriz](../results/e071_midpoint/summary.md).

## E072 — Radix local por bytes

**Medido.** Tres histogramas de hasta 256 entradas se forman juntos. Se pagan hasta tres repartos y dos auxiliares reutilizables de hasta 128 KiB cada uno. La ruta de tres pasadas escribe directamente al array en la última. Con la cobertura de E069, el candidato tarda 124,66–126,27 ms en uniforme y 117,71–118,59 ms en prefijos amplios. El control `replay` tarda 30,02–30,65 ms. Las pérdidas pareadas son 92,44–95,86 ms y 87,10–87,93 ms respectivamente. El tiempo combina detección, histogramas, pasadas y materialización. La tanda no aísla la causa de la pérdida ni mide tráfico físico. 84 tiempos, 96 salidas exactas contando calentamientos, 32 capturas exactas y 4.806 comprobaciones previas. Se cierra el kernel. [[E072 - Prerregistro radix local por bytes]]. [Matriz](../results/e072_radix8/summary.md).

**Cierre de E069–E072.** 336 tiempos, 384 salidas exactas de los brazos, 128 capturas exactas y 19.224 comprobaciones previas. Las cuatro tandas fallan la puerta para integrarse. E071 ahorra en las cuatro entradas, con déficit de 4,24–5,06 ms hasta la meta. El siguiente contraste distingue volumen de partición, hojas y respaldo de E071. Si los respaldos con ambos lados no vacíos tienen presupuesto, probar terminar los dos lados con vqsort y conservar el corte ya hecho. Acumulado del índice 287.213 tiempos y 328.864 salidas comprobadas. No hay procesos en ejecución. [Mejor ahorro local E071](../results/e071_midpoint/summary.md).
