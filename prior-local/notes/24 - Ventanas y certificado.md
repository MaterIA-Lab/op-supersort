# Ventanas de multiplicidades con respaldo general

## Correctitud y presupuesto

El sorter devuelve el resultado en el mismo array `uint32_t`, un hilo, sin payload ni estabilidad. La muestra elige candidatos a ventanas alineadas de 65.536 valores. El prefijo alto determina exactamente la pertenencia. Con un intervalo ordenado o dos disjuntos, cada clave pertenece a lo sumo a una ventana. El certificado cuenta los externos y rechaza cuando el número observado cruza el límite. Ese número nunca disminuye. En rechazo, A no ha cambiado y vqsort recibe las n claves originales. Fuera de los tamaños de la ruta de conteo también se ejecuta vqsort.

En E047, un bloque declarado constante contiene solo copias de `A[0]`. Esas copias aportan cero externos cuando su prefijo está admitido. La comprobación de cobertura empieza en el primer bloque que puede contener otro valor. Si no existe, el array ya cumple el orden. Si el primer valor es externo y existe propuesta, alguna de las muestras pertenece a una ventana, por lo que hay al menos dos valores. Cada posición queda certificada, incluso en la cola parcial. Se puede releer un bloque de hasta 32 claves al pasar a la ruta general del certificado.

Si se acepta, la clasificación reconstruye el multiconjunto en los contadores y el vector de externos. Cada aparición incrementa una celda o se escribe una vez al vector. La capacidad de cada contador cubre n en la rama de conteo. Se ordenan los externos y se copian por tramos antes de, entre y después de las ventanas. Emitir las ventanas por prefijo y sus valores por índice ordena todas las apariciones conservando duplicados. No se vuelve a leer el array original después de empezar a escribir. El espacio dinámico de esta ruta, aparte del respaldo sobre el residual, es de 256 o 512 KiB para contadores y cuatro bytes por externo, hasta unos 5,52 MB decimales en 10M. Es capacidad de buffers, no memoria residente ni tráfico medido. El código de prueba y el certificado usan AVX2 en el entorno x86 fijado.

El coste de reconstruir el orden de las ventanas es recorrer contadores y emitir n claves. Se eliminan las particiones y redes para las apariciones contadas. La ganancia práctica depende de la densidad, el coste de las dos lecturas y la dispersión de los contadores. Un conjunto con cuatro prefijos altos de 8 bits y sufijos amplios puede ser concentrado en esos 8 bits sin ser denso en ninguna ventana de 16 bits. Un muestreo favorable con una cola hostil puede pagar la lectura entera y el respaldo. La matriz distingue ambos casos. Esta combinación comparte ideas con conteo por rango y separación de claves frecuentes. [[11 - Literatura y límites de novedad]].

## E046 medido

WSL, Ryzen 7 5800X, GCC 11.4, CPU lógica 2. El conteo ganó a la misma detección seguida de vqsort y a vqsort directo en ambas semillas de `dense16`, `skew` y `bimodal`. La ganancia neta frente a vqsort fue 1,71–2,62×. El adversario de rechazo tardío pagó 2,20–2,76 ms adicionales. `equal` perdió 0,28 ms en ambas semillas. En un `few` que delegó al mismo vqsort, el candidato perdió 2,48 ms. El filtro completo falló. La causa de la pérdida de `few` queda abierta. [Datos E046](../results/e046_windows_filter/summary.md).

El orden de pivotes de la biblioteca puede variar entre llamadas y procesos por el estado inicial y su avance. E047 controla esa fuente de variación en el filtro para estimar el coste de detectar y delegar con un mismo estado inicial. La comparación completa condicionada conserva el comportamiento habitual de los pivotes. [[E047 - Prerregistro certificado por bloques]].

## E047 filtro con estados emparejados

El filtro pasa sus condiciones en 20 entradas. A 10M, frente a vqsort directo, `dense16` gana 2,57–2,73×, `skew` 1,64–1,83× y `bimodal` 2,17–2,18×. Las dos constantes se certifican en 1,76–1,78 ms frente a 1,91–1,99 ms. El rechazo tardío cuesta 1,56–3,99 ms adicionales. Ambos `few` pasan la puerta y delegan a vqsort. El experimento usa dos semillas nuevas y el certificado nuevo además de los estados de pivote emparejados, así que el contraste entre etapas no demuestra la causa del `few` de E046. 54 comparaciones de guardas y 480 salidas exactas del filtro con calentamiento. [Tabla E047](../results/e047_windows_filter/summary.md).

## E047 comparación completa

El binario del filtro se usó con sus hashes verificados. En la comparación completa se dejó el estado normal de pivotes de las referencias. Se cobró desde la entrada hasta la salida in situ, incluidas detección, auxiliares, copias internas y respaldo. 48 entradas nominales, 1.344 muestras, 1.536 salidas exactas con calentamientos. `equal` repite el mismo array entre semillas y cada pareja de intercalación comparte multiconjunto. Comparadores fijados vqsort estático, x86-simd-sort estático e IPS2Ra secuencial, un hilo y la misma máquina. [Tiempos por entrada y todos los negativos](../results/e047_windows_full/summary.md).

| Familia a 10M | Mediana E047 por semilla | Factor frente a mejor referencia por entrada |
|---|---:|---:|
| `dense16` | 12,96–13,93 ms | 2,78–2,81× |
| `skew` | 15,24–18,82 ms | 1,68–1,89× |
| `bimodal` | 12,90–15,00 ms | 1,92–2,08× |
| Dos ventanas intercaladas | 12,80–12,91 ms | 2,07–2,15× |
| Dos ventanas concatenadas | 13,53–14,98 ms | 2,10–2,43× |

14 de 24 entradas nominales tienen la menor mediana a 1M y también a 10M. Las cinco familias de la tabla ganan las dos semillas a ambos tamaños. Uniforme, `mixed` y `prefix_distinct` usan vqsort tras el probe. Sus diferencias de mediana con vqsort directo no demuestran una ordenación más rápida en esa ruta. En 10M, el adversario tarda 1,87–3,23 ms más que vqsort. Ambas `equal` pierden ante vqsort por 0,20–0,26 ms, aproximadamente 13–17%. Ambas `few` y ambas `near_sorted` pierden frente a la mejor referencia. Las intercalaciones conservan el orden de las claves dentro de cada ventana. Sus tiempos comparan orden de llegada con trabajo de clasificación equivalente, sin atribuir diferencias a un nivel físico de caché.

La ganancia medida cubre ventanas densas, sesgo con 5% de dispersión y dos modos separados. La mezcla mitad densa y mitad uniforme y los prefijos amplios conservan el comportamiento del respaldo. Solo se midió una máquina AVX2 bajo WSL, con dos semillas por familia y tamaño. El efecto de las ventanas desalineadas, 100M, otros procesadores y consumo físico de memoria permanece abierto.

La entrada C++ está en `include/supersort/windows_e047_u32.hpp`, función `supersort::window_e047_u32(a, n)`. Usa `vq_sort_u32` de la integración Highway del repositorio. Las llamadas del sorter devuelven contadores de diagnóstico que el usuario de la función puede ignorar. El runner archivó el comando de compilación y los hashes del binario y sus dependencias. [Metadatos del binario](../results/e047_windows_filter/metadata.json), [muestras completas](../results/e047_windows_full/raw.csv).

## Siguiente contraste

La mezcla mitad densa y mitad dispersa queda fuera por construcción. Ampliar el presupuesto por sí solo obliga a clasificar y copiar hasta media entrada y puede eliminar el margen. Antes de cambiarlo, aislar el coste de compactar externos con máscaras AVX2 y tablas de permutación sobre las mismas ventanas y el mismo certificado. El control conserva la clasificación escalar, el mismo sort del residual y la misma emisión. Comparar máscaras de todo admitido, alternancia e intercalación aleatoria a cobertura idéntica, cobrando todos los stores y las colas. Si la compactación no ahorra una parte sustancial en la mezcla intercalada o perjudica el caso 95/5, la variante se descarta antes de cambiar la política. Es una hipótesis, sin tiempos ni trabajo en curso.
