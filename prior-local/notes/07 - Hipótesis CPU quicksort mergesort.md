# Hipótesis CPU: quicksort y mergesort

2026-11-05. [[E034 - Prerregistro]] separa validación de selección. Esta nota separa mecanismo, predicción y criterio de descarte. No hay novedad ni mejoras nuevas de mergesort demostradas.

## Modelo de trabajo

Tiempo aproximado = clasificación + movimientos + hojas + control adaptativo. No sumar como costes independientes cuando se solapan en CPU: el modelo sirve para diseñar contrastes, no para predecir ciclos exactos. Comparaciones, bytes lógicos y fallos de rama son observables distintos. El coste depende de dependencias entre instrucciones, localidad y paralelismo de accesos, además de su cantidad.

Para buckets: T(K) ≈ scatter(n,K) + sum_b C(m_b) + copia(n) + reserva(K*cap). En uniforme m_b tiene marginal Binomial(n,1/K); Poisson(n/K) aproxima sus colas. Aunque las ocupaciones están correlacionadas, la linealidad permite E[sum C(m_b)] = K E[C(m)]. Si C es escalonado, C(E[m]) no sustituye a E[C(m)]. Aumentar K reduce cruces de redes pero aumenta estado y destinos activos; no extrapolar la ventaja a millones.

## Q1 — quicksort: elegir hojas por coste, no solo por longitud

Mecanismo: partición SIMD seguida de redes pequeñas elimina ramas impredecibles; una red sobredimensionada hace trabajo en lanes de relleno. Hipótesis: dos niveles de hojas o redes de tamaño intermedio podrían ahorrar comparaciones/permutaciones sin aumentar demasiado código y presión de registros. No basta cambiar K del bucket sort para demostrarlo.

Predicción falsable: el coste de ordenar hojas uniformes muestra saltos cerca de 64/128/256; el ahorro debe sobrevivir dentro del quicksort completo, incluida selección de pivote y partición. Contraste futuro: mismo quicksort upstream, única variación en dispatch/red de hoja; longitudes alrededor de cada frontera, duplicados, ordenados y reverse. Referencias vqsort, x86-simd-sort y pdqsort. Si baja el microcoste y sube el total, rechazar la variante total: posible presión de instrucciones, no atribución probada.

## Q2 — quicksort: partición por bloques con decisión adaptativa

Mecanismo: clasificar un bloque, registrar posiciones y mover después desacopla decisiones de ramas dependientes de cada clave. Ya es una idea de BlockQuicksort y pdqsort, no una invención nuestra. La adaptación candidata debe decidir si compensa una partición simple cuando la rama es predecible. El balance de valores NO mide por sí solo predictibilidad: secuencias agrupadas y alternantes pueden tener el mismo histograma.

Predicción: con idéntico multiconjunto, variar el orden (agrupado/alternante/aleatorio) cambia el beneficio del bloqueo. Una muestra debe medir transiciones además de balance; su coste y errores se incluyen. Antes de proponer selector, medir ramas/ciclos o al menos contrastes de orden controlado. El baseline branchless competitivo es obligatorio: ganar solo a std::sort no basta. Mantener profundidad acotada y tratamiento de iguales; no sacrificar peor caso por muestreo.

## M1 — mergesort: adaptar al orden existente

Mecanismo: detectar runs cuesta O(n), pero puede evitar niveles completos de mezcla cuando ya existen tramos largos. Con longitudes r_i, minimizar sum r_i*profundidad_i reduce volumen lógico de movimientos; Powersort ya aborda esa política. Proponer otro árbol sin compararlo con Powersort sería un baseline insuficiente.

Predicción: ventaja crece con runs largos y desiguales; aleatorio puede perder por detección y metadatos. Matriz futura: mismo conjunto de claves con runs de 32/256/4096 y longitudes desiguales, sawtooth, alternancia, pocos swaps y datos aleatorios. Separar política del árbol y kernel de mezcla: no cambiar ambos a la vez. En esta fase no prometer estabilidad por usar std::merge; si las hojas SIMD reordenan registros iguales, cambiaría el contrato con payload.

## M2 — mergesort: mezcla por bloques y copia final

Mecanismo: dos streams secuenciales facilitan prefetch y SIMD; alternar buffers por nivel puede evitar copias redundantes. El tráfico lógico de una pasada completa es aproximadamente 8*n bytes (leer y escribir uint32), sin equivaler a bytes DRAM. Reservar, inicializar y devolver al array original sigue dentro del tiempo.

Hipótesis concreta para el siguiente candidato: hojas fijas SIMD + merges binarios ping-pong + omitir una mezcla cuando max(izquierda)<=min(derecha), copiando si el destino del nivel lo exige. Ese test no elimina automáticamente tráfico cuando alternamos buffers. Probar primero frente a la MISMA variante sin test; después natural runs frente a Powersort. Riesgo: mezcla escalar con ramas impredecibles y más pasadas pierde frente a quicksort SIMD, aunque los accesos sean secuenciales. Un resultado negativo es útil para localizar el límite.

## Orden de decisión

1. Cerrar E034 sin retocar ganador por plataforma o entrada.
2. Medir ocupación y coste de hojas para distinguir explicación de coincidencia.
3. Implementar M2 como contraste único registrado, conservando std::stable_sort y Powersort como referencias antes de afirmar mejora en mergesort. Añadir datos con runs; la matriz actual no cubre ese eje.
4. Solo promover una adaptación si supera el coste de observar datos en holdout y no introduce regresiones inaceptables. No hacer barrido amplio y llamar algoritmo al mínimo retrospectivo.

## Fuentes primarias consultadas

- [Edelkamp y Weiß, BlockQuicksort](https://arxiv.org/abs/1604.06697): separación de clasificación y movimientos para reducir mispredicciones.
- [Munro y Wild, Nearly-Optimal Mergesorts](https://arxiv.org/abs/1805.04154): adaptación a runs y orden de mezclas.
- [Código de Powersort y Multiway Powersort](https://github.com/sebawild2/powersort): referencia que debe fijarse por commit antes de integrar.
- Código local fijado x86-simd-sort: src/xss-network-qsort.hpp, sort_n_vec reduce vectores cuando N*2 <= numVecs*numlanes. Esto respalda que hay escalones, no prueba que expliquen todas las regresiones observadas.


## Lo aprendido al concretar E035/E036

E035 mide un salto 129/128 de 3.166x Windows y 3.364x Ubuntu en hojas aisladas, no solo un aumento suave proporcional a N. La red mayor usa más variables vectoriales y operaciones. AVX2 tiene un presupuesto de registros limitado; spills son una explicación adicional posible que requiere inspeccionar ensamblado y/o contadores, no está demostrada aquí.

M2 preserva recorridos por nivel incluso al omitir comparaciones: copiar tramos ya ordenados sigue consumiendo ancho de banda. En un run de 4096, hojas128 implican cinco niveles inferiores que podrían ahorrarse con detección de runs naturales, pero con M2 aún se copian. De ahí la razón para probar después una política natural frente a Powersort en vez de seguir ajustando tamaños a ciegas. Un único run global tiene un límite inferior práctico lineal para validarlo; ordenar hojas y copiar log niveles hace trabajo innecesario.

No basta decir que mergesort tiene buena localidad: en mezcla aleatoria la elección entre las dos cabeceras puede resultar impredecible y el kernel escalar hace una decisión por salida. SIMD puede reducir ese coste, pero las permutaciones y colas requieren medir el kernel y el sorter completo por separado. Árbol de runs, hoja y kernel son tres ejes distintos; tocar los tres juntos impide atribuir el resultado.


## E037: lo que refuta y lo que apoya

Detectar runs elimina niveles: sorted/equal llegan a0 y runs4096 pasa10→5 en73001. Sin embargo, en ese último caso ambos ejecutan342610 salidas de mezcla: la mejora solo evita hojas/copias inferiores. Dos casos runs4096 no ganan siquiera al control, por lo que falla el criterio estricto registrado. No asumir que eliminar niveles elimina comparaciones costosas en la misma proporción.

En run_heavy73001/4243, escrituras totales por niveles bajan730010→584008, mientras elementos mezclados suben306637→578023; el tiempo empeora. El coste de escribir mediante std::merge no equivale al de copiar un tramo ya ordenado. Es evidencia para separar esas cantidades, sin atribución de todos los ciclos ni diagnóstico de caché. Próxima propuesta en [[08 - Árbol de mezclas y movimientos]]: mismo ejecutor para comparar árboles por longitudes, evitando confundir esa política con ping-pong/copia final.
