# Compactación y separación de externos

## E048 — Clasificación preparada

E048 compara la misma ventana conocida y las mismas secuencias de claves, con el escalar de E047 y una variante AVX2 que compacta ocho claves por máscara. Solo entran al reloj reserva, inicialización y clasificación. Cada llamada se comprueba contando, comparando el residual estable y reconstruyendo la salida completa contra `std::sort` fuera del tiempo. 2.248 verificaciones previas con guardas, 252 muestras y 288 salidas exactas con calentamientos. [Prerregistro](E048%20-%20Prerregistro%20compactación%20AVX2.md), [matriz y muestras](../results/e048_compact_filter/summary.md).

| Entrada a 10M | Escalar | AVX2 | Cociente escalar / AVX2 |
|---|---:|---:|---:|
| 50/50 aleatoria, una ventana | 29,14–29,37 ms | 11,95–11,98 ms | 2,44–2,45× |
| 50/50 aleatoria, dos ventanas | 30,92–31,24 ms | 12,74–12,76 ms | 2,43–2,45× |
| 95/5 aleatoria, una ventana | 7,92–8,47 ms | 7,81–7,88 ms | 1,01–1,07× |
| 95/5 aleatoria, dos ventanas | 33,45–33,73 ms | 10,84–11,29 ms | 2,99–3,09× |
| 50/50 periódica, semilla 23143 | 6,10 ms | 7,71 ms | 0,79× |

La puerta falla en la entrada periódica anterior. Las demás entradas con externos pasan sus límites. A igual multiconjunto, el escalar cambia de unos 6 a unos 29 ms al cambiar la intercalación periódica por aleatoria. La clasificación AVX2 también cambia de tiempo. La predicción de ramas es una explicación posible, no una causa establecida por contadores. Incluso en el control `inside`, donde ambos brazos llaman al mismo `count_all`, las medianas difieren. Las pequeñas diferencias no se interpretan como ahorro de trabajo. Se conserva el kernel como brazo diagnóstico. E047 sigue usando su separación original y su presupuesto.

## Alternativa estructural

E049 separa inferiores y superiores directamente hacia ambos extremos del array y mantiene el conteo en el centro. Sustituye el buffer de externos y su copia de vuelta por dos cursores, dos máscaras y hasta dos stores por bloque. Divide el sort residual por rangos de valor. La ventana se conoce en el diagnóstico. La propuesta y el rechazo de un sorter general quedan para una prueba posterior si la ruta conserva margen. El argumento de los dos huecos y las colas de 23 claves figura en el prerregistro. La partición vectorizada in situ tiene antecedentes en el trabajo de Blacher, Giesen y Kühne. El experimento mide esta combinación con conteo, no establece prioridad sobre sus componentes. [Prerregistro E049](E049%20-%20Prerregistro%20separación%20in%20situ.md), [Fast and Robust Vectorized In-Place Sorting of Primitive Types](https://doi.org/10.4230/LIPIcs.SEA.2021.3).

## E049 — Separar hacia los extremos

El invariante de huecos mantiene la suma de espacios libres en 16 o más tras cada vector procesado. Antes de las escrituras se carga un vector desde el lado con menos hueco y quedan ocho posiciones de escritura por lado, disjuntas de todo lo pendiente. El histograma captura cada interno antes del store. Los buffers de los extremos se ordenan por separado y la suma de sus tamaños determina exactamente la longitud del hueco de emisión. Se elimina el buffer de `4r` bytes, con unos 20 MB en 50/50 a 10M. Quedan 256 KiB de contadores, una cola de hasta 23 claves y la memoria que use vqsort. No hay estimación de RSS. [Prerregistro E049](E049%20-%20Prerregistro%20separación%20in%20situ.md).

En las dos 50/50 agrupadas y periódicas, el candidato gana a vqsort por 1,22–1,39× con la ventana conocida. En las 50/50 aleatorias gana a ambos brazos con buffer pero tarda 37,88–38,58 ms frente a 36,67–36,85 ms de vqsort. Requería al menos 1,10× y pierde ambas. También incumple un 95/5 frente a la separación escalar, cociente 0,898790. El filtro falla. Se validan 4.916 comprobaciones previas y 384 salidas con calentamientos. No se amplía la política de E047. [E049 y todos los negativos](../results/e049_split_filter/summary.md).

E050 compara un cursor hacia delante con la separación por extremos. Elimina el segundo flujo, la segunda máscara y la segunda escritura potencial, a costa de desplazar el tramo alto al final. Añade un modo separado para medir dónde se gana y qué se paga. [[E050 - Prerregistro cursor y fases]].


## E050 — Un cursor, menor coste de clasificación

En la ruta de cursor único, el índice de escritura es el número de externos anteriores. No supera al índice de lectura. Al cargar un vector y contar los internos antes del store, incluso una escritura de ancho completo alcanza como máximo la última posición del bloque leído. El residual estable ocupa el prefijo. Tras ordenarlo, el tramo inferior ya está en su lugar. `memmove` lleva el superior al final, y el histograma llena exactamente el hueco. Se conserva la reserva de 256 KiB de contadores y se evita el buffer de `4r` bytes. [[E050 - Prerregistro cursor y fases]].

Las mezclas 50/50 aleatorias de 10M bajan a 35,68–35,96 ms frente a 36,87–36,89 ms de vqsort. Los dos cocientes 1,025 y 1,034 quedan por debajo de 1,10. Pasan los otros límites. Son tiempos con la ventana preparada. No se añade esta ruta al sorter general. 336 muestras, 384 salidas exactas y 4.916 comprobaciones previas. [Matriz E050](../results/e050_forward_filter/summary.md).

En el diagnóstico de una semilla, clasificar la 50/50 aleatoria baja de 15,28 a 12,23 ms frente a los dos extremos. El sort residual sube de 20,69 a 21,59 ms y la reconstrucción cambia de 1,49 a 1,53 ms. Con todos los externos altos, reconstruir sube de 1,48 a 2,12 ms. A igual multiconjunto, la clasificación de cursor único varía de 5,10 ms en periódica a 12,23 ms en aleatoria. Los tiempos no identifican la causa física. 70 llamadas medidas con relojes internos y 80 salidas exactas. [Fases y datos](../results/e050_forward_filter/phases.md).

E051 conserva el cursor y cambia solo la clasificación. El coste fijo por clave elimina la enumeración variable y la permutación, a cambio de stores redundantes y un histograma auxiliar descartado. La entrada con un mismo externo repetido prueba la dependencia de ese histograma. [[E051 - Prerregistro clasificación de coste fijo]].


## E051 — Coste fijo y pérdida de adaptatividad

La clasificación escalar de coste fijo cumple el mismo invariante del cursor. Un store de una interna deja una clave provisional en la siguiente posición libre. El residual solo crece tras un store externo. Cada interna incrementa exactamente su contador real. Cada externa incrementa un contador de descarte en 1 KiB aparte, sin influir en la emisión. El binario compilado contiene dos instrucciones setne, un incremento de contador, un store de clave y un salto de fin de bucle, sin salto dependiente de la clase de la clave. El ensamblado no mide ocupación de buffers, ancho de banda ni ciclos. [Ensamblado archivado](../results/e051_shadow_filter/assembly-shadow.stdout.txt).

En la tanda E051, el clasificador de coste fijo con reconstrucción para 50/50 aleatoria tarda 33,21–33,82 ms frente a 35,90–36,37 ms de vqsort, 1,075–1,081×. Falla 1,10 en ambas semillas y las dos 95/5 quedan un 20–23% por detrás de la separación escalar con buffer. Pasa el adversario de un externo repetido frente al cursor AVX2. No integrar el candidato. 392 tiempos, 448 salidas exactas con calentamiento y 4.916 comprobaciones previas. [E051 y negativos](../results/e051_shadow_filter/summary.md).

En las fases de la 50/50 aleatoria, el clasificador baja de 11,77 a 10,40 ms. En la periódica sube de 5,56 a 10,40 ms y en 95/5 sube de 7,01 a 10,27 ms. Para la aleatoria, el sort residual de 21,72 ms es la fase mayor y reconstruir cuesta 1,54 ms. Con un externo repetido, el sort residual baja a 0,93 ms y la clasificación con descarte tarda 10,94 ms frente a 11,73 ms de forward. La hipótesis de una pérdida decisiva por repetición no se observa en ese adversario. Los datos permiten distinguir costes por fase, no repartir ciclos entre escrituras, dependencias y aritmética. 56 llamadas medidas con relojes internos y 64 salidas exactas. [Fases E051](../results/e051_shadow_filter/phases.md).

## Siguiente punto de decisión

Mantener E047. Las tres reorganizaciones preparadas de la 50/50 muestran que reducir clasificación y eliminar el buffer del residual no dejan el margen fijado, antes de pagar la decisión. La fase más larga ordena cinco millones de externos del ancho completo. El próximo contraste puede aislar un reparto grueso que sustituya las primeras particiones de ese sort. Probar el mismo residual de 5M con vqsort completo y con un reparto por prefijo seguido del mismo vqsort por tramos. Cobrar histograma, reserva, scatter, sort local y materialización en el array residual. Incluir uniformes, prefijos concentrados, mezcla y externos de un solo lado. Como filtro de descarte, el mecanismo preparado debe recuperar al menos 4 ms en los residuales de las dos 50/50 aleatorias. Eso cubre el déficit preparado y deja unos 3,2–3,4 ms de margen para la comprobación. Su coste real se tendría que medir. Si pasa, estudiar si fusionar el histograma con el certificado evita pagar otro recorrido, y probar el sorter completo con la misma política y su respaldo. Es una hipótesis pendiente, sin estimación física de caché ni tiempo medido.
