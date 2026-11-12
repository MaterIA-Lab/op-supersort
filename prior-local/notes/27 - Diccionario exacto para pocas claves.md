# Diccionario exacto para pocas claves dispersas

## Invariante

El muestreo solo propone de dos a dieciséis valores. Se eligen hasta ocho bits cuya proyección distingue todas las propuestas. Para cada proyección se almacena la clave completa. Al consultar, una coincidencia de proyección no basta. Se verifica el valor completo de cada aparición. Rellenar una ranura vacía con la primera propuesta es seguro porque esa clave siempre consulta su propia proyección. Si alguna clave discrepa del testigo, A permanece intacto y se delega a vqsort. Si todas coinciden, la suma de contadores vale n y emitir en orden de valor conserva el multiconjunto. La réplica de cuatro tablas cambia la dependencia entre incrementos. La suma al final sigue representando cada aparición exactamente una vez.

La propuesta admite proyecciones de hasta ocho bits. Hay diccionarios reales que necesitan más para esta estrategia. El conjunto con cero y quince potencias de dos activa ese caso. Una clave nueva tardía puede pagar casi una lectura y luego ordenar todo el array. El rango de tamaño de esta ruta permite contadores `uint32_t`. El kernel medido usa BMI2 y el entorno AVX2 del proyecto. [[E053 - Prerregistro diccionario por bits]].

## E053 medido

A 10M, la variante de cuatro tablas tarda 7,35–8,12 ms en las cuatro entradas `few` y `few_permute`, con cocientes de 1,54–1,67× ante vqsort directo. En `few_dominant` gana 1,86–2,05× frente a una sola tabla y 1,15–1,17× frente a vqsort. Para hacer efectivo el contraste de dependencias se garantiza que cada valor minoritario aparezca en alguna posición muestreada de esa familia. La réplica pierde una de las dos permutadas frente a la tabla única. No se sostiene que cuatro tablas ganen siempre.

El adversario temprano examina cuatro claves y delega. El tardío examina 10M y añade 3,35–4,67 ms frente a vqsort. Ambos comparten multiconjunto. El probe de la variante en `few_powers` no consigue una proyección y sale por colisión sin escaneo completo. Pasa el filtro prerregistrado, con 270 comprobaciones previas, 378 tiempos y 432 salidas exactas con calentamientos. [Tabla y datos E053](../results/e053_dictionary_filter/summary.md).

## Integración condicionada

E054 prueba E047 y el diccionario juntos. Una propuesta de ventanas conserva su ruta. El diccionario solo se intenta tras un probe de ventanas vacío. Esta política cobra dos probes en esos casos y a lo sumo un certificado de array entero. La tabla de 25% se evalúa frente a la mejor referencia externa por caso, con estados de pivotes normales y semillas nuevas. [[E054 - Prerregistro compuesto con diccionario]].

## E054 medido a 10M

786 comprobaciones previas con guardas, 1.260 muestras y 1.440 salidas exactas con calentamientos. Ubuntu WSL, Ryzen 7 5800X, CPU lógica 2, GCC 11.4, AVX2/BMI2. Se midió el sorter completo, incluidas las decisiones. Las tres referencias fueron los modos de un hilo fijados de vqsort, x86-simd-sort e IPS2Ra. [Matriz por caso, pérdidas y metadatos](../results/e054_combined_full/summary.md).

| Familia | Mediana del compuesto | Factor ante la mejor externa por entrada | Ruta |
|---|---:|---:|---|
| `few` | 7,35–7,91 ms | 1,58–1,60× | Diccionario |
| `few_permute` | 7,45–7,70 ms | 1,49–1,50× | Diccionario |
| `dense16` | 12,77–12,95 ms | 2,71–2,72× | Una ventana |
| `skew` | 14,36–14,84 ms | 1,73–1,76× | Una ventana |
| `bimodal` | 12,28–13,46 ms | 2,00–2,22× | Dos ventanas |

Cobertura nueva de 25% en las cuatro `few` y `few_permute`. Diez de 22 entradas principales cumplen 1,25. La meta general queda abierta. Los dos uniformes, los dos prefijos amplios y ambas mezclas 50/50 delegan a vqsort tras los probes. Las dos `equal` y las dos `few_powers` tampoco llegan a 1,25. En `few_dominant`, la prioridad de ventanas elige un conteo más lento que el diccionario autónomo. El compuesto tarda 13,16–13,29 ms frente a 8,19–8,47 ms del diccionario y 8,58–9,12 ms de la mejor referencia externa. El diccionario autónomo tampoco alcanza 1,25 en esa familia. El rechazo tardío del diccionario añade 3,06–3,62 ms frente a vqsort en las semillas de esta tanda.

En uniforme, 1,25 en esta tanda da unos 38,17–39,08 ms, frente a 48,41–48,66 ms del compuesto. La mezcla mitad densa y mitad dispersa necesitaría aproximadamente 30,43–30,95 ms frente a 37,24–38,35 ms. No se pueden sumar tiempos de fases entre tandas como predicción. Esos presupuestos muestran que las diferencias pequeñas de probes o un retoque de hojas no son una explicación suficiente del hueco.

## Decisiones para el siguiente contraste

La elección de ventana en `few_dominant` es un fallo concreto de política. Un detector que ya ha propuesto de dos a dieciséis valores con proyección válida puede elegir el diccionario antes de una ventana. Si ambas propuestas son posibles, esa prioridad debe pasar un contraste sobre entradas nuevas, con un solo certificado de datos completo y cobrando la decisión. En entradas que muestran pocas claves pero ocultan una cola amplia, la validación exacta sigue decidiendo la salida.

También se puede aprovechar un rechazo tardío. Si el diccionario ha contado k posiciones iniciales completas y una clave posterior falla, esas k apariciones ya están representadas. Ordenar solo la cola restante en A[k:n]. Emitir hacia delante, copiando con `memmove` los tramos de cola entre las claves del diccionario y luego las multiplicidades del prefijo. Después de consumir t elementos de cola y emitir c del prefijo, el cursor vale t+c y la lectura pendiente comienza en k+t. Como c≤k, ninguna escritura pisa la cola todavía necesaria. Tras emitir las k apariciones, el tramo final de cola ya está en su lugar. Se elimina ordenar de nuevo el prefijo a cambio de una reconstrucción y posibles desplazamientos de la cola. Medir rechazos tempranos y tardíos, más cola adversaria grande, con la misma propuesta en ambos brazos. Mantener esta idea como hipótesis.

La brecha principal de uniforme y prefijos amplios sigue en la ruta de alta entropía. Se prioriza una partición que elimine un recorrido completo, con un contraste que mida distribución y hojas por separado antes de integrarla. E052 ya indica que ahorrar un recorrido pequeño no compensa mantener toda su geometría de hojas. La comparación amplia requiere también una referencia radix reciente en el mismo entorno. F5 sigue pendiente de una implementación reproducible accesible. [[26 - Meta del 25 por ciento y hojas compactas]].
