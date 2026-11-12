# Correctitud y límites

## Reparto predictivo

El prefijo de H bits define intervalos de claves ordenados. Cada clave se guarda una vez en su bucket, con un contador que delimita exactamente los slots válidos. Ordenar cada bucket y concatenarlos produce el orden global; no depende de uniformidad.

La capacidad prevista es una optimización, no una precondición. Se comprueba antes de cada escritura. Si falla, el original todavía no ha sido modificado y se entrega entero al fallback SIMD. Durante la concatenación ya no puede producirse overflow. Los huecos sin inicializar nunca se pasan como elementos válidos a la ordenación local.

Memoria de predict10shiftraw en n=100.000: media ceil(100000/1024)=98, capacidad 161 uint32 por bucket, 164.864 slots = 659.456 bytes, más 8.192 bytes de contadores, excluyendo overhead de asignador y pila del sorter SIMD. La memoria auxiliar no es in-place.

## Selector

La muestra puede equivocarse. Solo elige entre algoritmos exactos. Una muestra monótona obliga a verificar todo el array antes de devolverlo o invertirlo. El caso samplemiss fuerza un escenario que el muestreo no detecta; el control de capacidad sigue evitando escrituras fuera de rango y resultados incompletos.

## Stores no temporales

Los destinos iniciales de buckets no suelen estar alineados. El primer fragmento se escribe de forma ordinaria hasta alcanzar una frontera de 64 bytes; solo las líneas completas interiores usan stores NT. La cola se escribe de forma ordinaria. Ninguna línea NT contiene slots de dos buckets, y se emite sfence antes de consumir el resultado. Las pruebas exactas cubren longitudes alrededor de las fronteras de 16/32/64 elementos.

## Qué no está demostrado

- No hay prueba formal. E031 pasa ASan/UBSan en 1.260 comprobaciones del reparto predictivo y scatter NT, con guardas y offsets; no cubre todas las variantes del benchmark ni todas las bibliotecas upstream.
- No hay novedad algorítmica establecida. Buckets, capacidad sobrante, SIMD y fallback tienen antecedentes.
- No hay victoria general sobre las bibliotecas punteras en distribuciones/tamaños/máquinas arbitrarios.
- Una diferencia mínima entre medianas no es evidencia suficiente de mejora: conservar dispersión y semillas, y validar fuera del conjunto de ajuste.
- Windows/GCC16 y WSL/GCC11 son entornos distintos. Comparar algoritmos dentro del mismo entorno.


## Mergesort E036

Cada hoja se ordena exactamente por SIMD. En cada nivel se mezclan dos tramos ordenados contiguos en un buffer distinto, o se copian si el segundo está vacío o max(izquierda)<=min(derecha). Ambos casos preservan el multiconjunto y el orden del tramo. Intercambiar buffers mantiene el invariante del siguiente nivel. La copia final devuelve el resultado al array original. Límites de tramos se calculan con min sobre longitud restante; duplicación de width protegida por n/2.

Scratch adicional n uint32 sin inicialización de huecos: toda posición se escribe antes de leerse; no hay huecos usados. Memoria O(n), reserva y copia final incluidas. Sin payload ni promesa de estabilidad: hojas SIMD no garantizan estabilidad de registros. 2280 comprobaciones pequeñas/frontera y12960 salidas de rendimiento pasan igualdad exacta con std::sort. ASan/UBSan de E031 NO cubre este nuevo kernel; no afirmar lo contrario.


## Runs naturales E037

Runs ascendentes permiten igualdad; descendentes son estrictos antes de reverse. Extender un run corto a128 y ordenar con SIMD preserva multiconjunto y produce un tramo ordenado. Descriptores contiguos cubren todo el array; su compresión escribe solo posiciones ya consumidas. Cada nivel mezcla fuentes y destino disjuntos, copia el run impar y escribe todas las posiciones antes del intercambio de buffers. Al final se copia si el resultado no reside en la entrada.

Memoria: vector de hasta ceil(n/128) pares size_t (16 bytes por descriptor en este entorno64bits), más scratch n uint32 si hay más de un run. Ambas reservas y liberaciones medidas. Un run único evita scratch pero no reserva de descriptores. n<2 devuelve antes de reservar. No se promete estabilidad/payload porque extensiones SIMD pueden reordenar registros iguales.

Correctitud exacta:5244 salidas iniciales y20064 del benchmark. Diagnóstico añade304 comprobaciones y verifica contadores lógicos, fuera de tiempo. ASan/UBSan e037_runs_sanitizers comprueba2484 casos con guardas y offsets de los dos kernels y wrapper Powersort, sin diagnósticos de ejecución. Cobertura limitada; no prueba formal ni prueba de estabilidad. La dependencia original de Powersort se conserva sin alteraciones; solo se usa en Linux y n<2 se evita en el wrapper.


## Árboles E038

Plan válido de r-1 ternas contiguas (lo,mid,hi). En weighted el poder se calcula antes de absorber stack; el orden de emisiones es postorder. Cada fusión consume dos intervalos ya ordenados, o se omite si frontera ordenada. Scratch separado y copyback evitan propiedad de buffers desigual. Sumandos de node power y duplicaciones protegidos por dominio n<=SIZE_MAX/2; n<2 devuelve. Pruebas6336 exactas iniciales,23232 de benchmark y352 instrumentadas; ASan/UBSan4140 casos incluyendo guardas/offsets, sin diagnósticos de ejecución.

Memoria en ABI64:16cap runs +24(cap-1) plan +16cap workspace con cap=ceil(n/128), más4n scratch si múltiples runs, reservas y liberación medidas. No estabilidad/payload por hojas SIMD. Los forzados aseguran mismos multiconjuntos mediante rotación tras sustituir extremos, sin centinela de mezcla (MAX es clave válida).


## Quicksort E040

Único delta byte-exacto en avx2_vector<uint32_t>::network_sort_threshold256→128. static_assert valida ese campo y conserva256enint32/float; AVX512/minimalnetworkmoderechazados. Bibliotecas privadas con versiones de templates locales y APIsCúnicas verificadas por readelf, evitando interposición en entornoELF. Se mantienen particiones, selección de pivote, tratamiento de iguales, profundidad y fallback upstream; no nueva prueba formal de biblioteca.

6336 salidas exactas de correctitud+21120 medidas/warmup.6624 casos de ASan/UBSan/guardas/offsets incluyen ambosDSOs instrumentados y kernels anteriores, sin diagnósticos de ejecución. Bibliotecas de rendimientoO3 separadas deO1instrumentadas; fuentes/flags/hashes/licencias archivadas por tag. El contrato sigue uint32 sin payload/un hilo/AVX2, memoria interna y fallback medidos; no inferir int32/payload/estabilidad ni otrohardware.


## E041, código idéntico

No cambia código nativo ni bibliotecas respecto aE040. SHA256debinario/DSOs y snapshots verificados antes y después.23760salidasexactasdelholdout y3120delrecheck; ASan/UBSan6624deE040es evidencia previa del mismo código, no se afirma nueva matriz de sanitizadores. Procesos nuevos y condicionesdeejecución no son idénticos solo por reutilizar bytes. Recheck no independiente y no sustituye fallos previos. No interpretar conteos como datasets independientes.

## E042–E044

E042 instrumentó copias separadas de los árboles archivados. Las 216 salidas O3 pasan igualdad exacta y guardas. La primera ejecución ASan/UBSan comprobó seis salidas triviales y quedó incompleta por `DEADLYSIGNAL` repetido en el segundo proceso vacío. Una recuperación registrada con las mismas DSOs sanitizadas y un host noPIE persistente completó 7464 comprobaciones exactas y guardas con stderr vacío. Se conservan la incidencia inicial y las dos configuraciones. [[13 - E042 trabajo y variación]].

E042-B y E043 verificaron antes y después el ejecutable E040 y sus DSOs. Son 30.720 y 3684 salidas exactas adicionales, con calentamientos. E044 usó un host nuevo y las mismas DSOs. Comprobó 192 salidas exactas, incluidas las rondas previas. Los 88 controles vacíos de la PMU no son salidas de sort. Ninguna de estas series introduce un nuevo algoritmo o un contrato de estabilidad. [[15 - Escala y contadores]].
