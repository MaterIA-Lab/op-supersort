# Meta del 25% y hojas compactas

El 25% se evalúa como rendimiento por unidad de tiempo. `T_mejor/T_candidato ≥ 1,25` equivale a `T_candidato ≤ 0,8 T_mejor`. La primera prueba general debe aplicarlo a cada caso principal de 10M y cada semilla, cobrando el sorter completo. La referencia por caso es la menor mediana entre vqsort, x86-simd-sort e IPS2Ra secuencial en la misma tanda. Ese criterio se puede reproducir. Una matriz finita no decide la comparación con todos los sorters ni con todas las entradas posibles.

La meta queda abierta en uniforme, mezcla 50/50, prefijos amplios y baja cardinalidad. En E047 uniforme y mezcla entran al respaldo y sus diferencias de medianas con vqsort no constituyen una ruta más rápida. E047 sí pasa 1,25 en ambas semillas de `dense16`, `skew` y `bimodal` de 10M ante las referencias incluidas. El nuevo presupuesto de la mezcla 50/50 es más estricto que E051. Con 35,90–36,37 ms de la referencia, queda un máximo de 28,72–29,10 ms para todo. Entre 10,40 ms de clasificación y 1,54 ms de emisión observados en el diagnóstico E051, la detección y el residual compartirían aproximadamente 16,8–17,2 ms. El ahorro residual de 4 ms de E052 es un umbral diagnóstico. [E047 completo](../results/e047_windows_full/summary.md), [E051 por fases](../results/e051_shadow_filter/phases.md).

## E052 medido

El histograma exacto y los dos niveles de reparto son iguales en el control y la variante. La representación de 16 bits es exacta porque el índice de la hoja conserva el prefijo descartado y la expansión recompone cada clave. La variante reserva menos memoria local, pero sigue pagando un buffer grueso cuando hay varios grupos. El cambio de anchura no produjo la mejora prevista en tiempo completo. [Prerregistro](E052%20-%20Prerregistro%20hojas%20de%2016%20bits.md).

| Familia | Claves | Hojas compactas | vqsort directo | Resultado |
|---|---:|---:|---:|---|
| Residual externo de todo el ancho | 5M | 35,92–36,13 ms | 23,24–23,58 ms | añade 12,34–12,88 ms por semilla |
| Uniforme | 10M | 80,12–81,01 ms | 46,93–48,41 ms | cociente 0,586–0,598 |
| Prefijos concentrados, sufijos distintos | 10M | 116,58–117,11 ms | 46,88–48,02 ms | cociente 0,402–0,410 |

En uniforme 10M, alrededor del 98% de las claves caen en hojas de más de 128 y ninguna en hojas de más de 256. La anchura cambia la posibilidad de usar redes, pero el cociente de tiempo `wide/packed` queda entre 0,985 y 1,025. Esto descarta el reparto más hojas compactas como candidato en esta implementación. No permite asignar la pérdida a la red, la dispersión, los histogramas o la emisión. El `dense16` alcanza una sola hoja gigante y tarda más en `packed` que en `wide`. La diferencia en esa hoja tampoco prueba por sí sola una causa del tiempo de uniformes.

408 comprobaciones de guardas, 546 muestras y 624 salidas exactas con calentamientos. Un error del analizador confundió claves con hojas después del quinto proceso. La recuperación verificó hashes y reutilizó las primeras cinco entradas, ejecutando solo las 21 pendientes. [Error original](../results/e052_packed_filter/failure.txt), [matriz recuperada y negativos](../results/e052_packed_recovery/summary.md).

## Referencias que faltan para una afirmación amplia

F5 de Arman y Loguinov combina saltos sobre prefijos comunes, distribución optimizada para ráfagas y redes SIMD de varios tamaños. El artículo publica resultados de un hilo para claves de 32 bits en varias máquinas y tamaños distintos de nuestra prueba. La página de Texas A&M ofrece el artículo y dice que el código se obtiene del autor. Aquí no hay una medición local de F5 ni un binario compatible archivado. La rama de alta entropía debe aspirar a compararse con radix especializados de ese nivel. [Artículo F5, §§V–VII](https://irl.cs.tamu.edu/people/arif/papers/icde2026.pdf), [página del proyecto](https://irl.cs.tamu.edu/projects/streams/).

E053 trabaja en la brecha de pocas claves dispersas. Su diccionario exacto intenta eliminar toda la ordenación comparativa para esa familia, con detección y respaldo cobrados. La ruta de alta entropía sigue como investigación separada. [[E053 - Prerregistro diccionario por bits]].


## Inspección estática de E052

El binario archivado contiene los caminos N_AVX2 de ambos tipos. Los puntos de entrada comparan con 128 claves para uint32 y 256 para uint16 antes de decidir la red o la recursión. Esta comprobación confirma el cambio de camino que podía habilitar el empaquetado. La red grande uint16 maneja más carriles y tiene más instrucciones estáticas, así que evitar un pivote no garantiza menos trabajo para esas hojas.

En la hoja gigante de dense16, el código fijado de compresión uint16 AVX2 divide el vector en mitades, comprime cada mitad y junta resultados con temporales de pila. El camino uint32 usa una permutación de carriles con tabla. Es un mecanismo plausible para parte de la pérdida de hojas grandes. Las hojas uniformes uint16 están bajo el límite de red y esa explicación no se traslada a ellas. Faltan contadores dinámicos o tiempos por fase. [Partición fijada](../results/e052_packed_filter/vendor/highway/hwy/contrib/sort/vqsort-inl.h), [operaciones fijadas](../results/e052_packed_filter/vendor/highway/hwy/ops/generic_ops-inl.h).
