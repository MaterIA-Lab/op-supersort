# Síntesis del reto y candidatos

2026-11-05. Síntesis de evidencia y análisis del prototipo existente. La contribución verificada consiste en mejoras de alcance acotado sobre técnicas conocidas. [[11 - Literatura y límites de novedad]] reúne la revisión actual. Los resultados recientes están en [[13 - E042 trabajo y variación]] y [[15 - Escala y contadores]].

## Restricciones que dominan el problema

El contrato vigente es CPU, un hilo, claves `uint32_t`, orden ascendente, sin payload ni estabilidad, salida en el array original. Se incluyen reserva, inicialización necesaria, liberación y copia final auxiliar en el tiempo; generación, copia común y comprobación exacta con `std::sort` quedan fuera. Cambiar estabilidad, conservar workspace entre llamadas o devolver la salida en otro buffer sería cambiar el problema medido.

Modelo de análisis: Word-RAM con operaciones sobre palabras de anchura suficiente para direcciones y contadores; claves de 32 bits, aritmética/bitwise/carga/almacenamiento de palabra de coste unitario. Para una familia asintótica de tamaños, la palabra de direcciones debe satisfacer `w >= ceil(log2(n+1))`; una máquina física con palabras de 64 bits tiene un dominio finito. SIMD AVX2 procesa ocho claves por vector; a anchura fija reduce constantes y no transforma por sí solo una cota en n. El coste unitario RAM tampoco representa latencias de caché, TLB, dependencias ni paralelismo de accesos.

La cota de comparación Ω(n log n) para n claves distintas no prohíbe radix o counting: esos algoritmos inspeccionan la representación y no se limitan al árbol de decisiones de comparaciones. Además, con universo fijo `U=2^32` no puede haber n claves distintas cuando n>U; no aplicar mecánicamente aquella prueba a ese dominio. Leer y materializar todas las claves exige Ω(n) trabajo para el contrato general. Ningún resultado del proyecto contradice esas cotas.

Con dígitos fijos de b bits, LSD radix tiene `ceil(32/b)` pasadas y cota `O(n + 2^b)` para esa anchura fija, más buffer O(n). Es un resultado conocido, no una mejora asintótica nuestra. Counting directo cuesta O(n+U) y necesita una tabla enorme: `2^32` contadores de 64 bits ocupan 32 GiB antes de entrada y salida. Usar 32 bits reduce a 16 GiB, pero limita el conteo de duplicados. Un bitmap de presencia ocupa 512 MiB y, por sí solo, pierde multiplicidades. Compresión o hashing no hacen desaparecer el coste de ordenar las claves distintas ni los casos adversarios de la estructura elegida.

En n=10.000.000 la entrada ocupa 40 MB decimales; en n=100.000.000, 400 MB. Cada buffer adicional del mismo tamaño vuelve a sumar ese volumen. Una lectura y escritura secuencial completa de uint32 representa 8n bytes lógicos, sin equivaler a bytes DRAM. En buckets dispersos, muchos destinos activos compiten por líneas, TLB y buffers de escritura. En redes SIMD importan también permutaciones, registros disponibles y tamaño de código. No basta minimizar el número de pasadas o de ramas.

## Candidatos priorizados y qué los haría fracasar

Son hipótesis formuladas para este laboratorio, **no reclamaciones de originalidad algorítmica**. Se ordenan por evidencia y valor del próximo contraste, no por el mejor tiempo observado retrospectivamente.

| Prioridad | Hipótesis / mecanismo | Evidencia actual | Contraste o descarte |
|---:|---|---|---|
| 1 | Q1: reducir red terminal 256→128 y pagar una partición adicional solo donde llegue el quicksort | E040 mejora todos sus random; E041 falla un random y robustez. Delta único e instrucciones archivados | Diagnosticar trabajo y variación entre procesos antes de promover. Si las regresiones persisten en alcance previsto, no usar sustitución universal. Es ajuste de un algoritmo conocido |
| 2 | M3: mezclar varios uint32 por decisión SIMD, manteniendo árbol y propiedad de buffers fijados | E039 demuestra que eliminar la rama escalar tiene margen pequeño en random y grandes pérdidas en few | Probar primero invariante de carry, extremos y colas; después mismo árbol con kernel de control. Descartar si microventaja no sobrevive al sorter completo. Mezcla SIMD tiene antecedentes |
| 3 | P1: reparto por prefijos con capacidad sobrante segura, hojas SIMD y fallback completo | Nicho mediano uniforme reproducido parcialmente; E034 no pasa su criterio estricto. A 10M pierde claramente ante vqsort | No añadir quick128 sin registrar candidato nuevo. Requiere margen neto después de reserva, scatter, hojas y copia; adversarios obligatorios. Es distribución optimizada, no paradigma nuevo |
| 4 | Q2: observar transiciones de clasificación para decidir partición por bloques | Idea previa en [[07 - Hipótesis CPU quicksort mergesort]]; no implementada ni medida | Mismo multiconjunto con órdenes agrupado/alternante/aleatorio. La muestra y sus errores deben pagarse; conservar límite de profundidad. BlockQuicksort/pdqsort son antecedentes directos |
| 5 | C1: construir diccionario exacto de pocas claves y emitir multiplicidades por orden de clave | Solo propuesta; no hay ventaja demostrada en el proyecto | Comparar con radix y sorters que ya tratan iguales. Auditar colisiones, overflow y fallback; medir entradas de alta cardinalidad. Counting/frequency sorting y estructuras de diccionario son conocidos |

No se adopta globalmente el kernel cmov de E039: random mejora aproximadamente 0,9–2,8%, pero few llega a 3,89x más lento y la robustez falla. E038 sí confirma el efecto del árbol ponderado sobre volumen y tiempos frente al mismo ejecutor; solo gana 2/176 nominales ante la mejor referencia externa. Detectar runs o usar Powersort no es un descubrimiento nuevo. Tampoco se busca otro umbral ganador mediante barrido y se presenta luego como holdout.

## Descripción precisa del candidato P1 implementado

Implementación: [predictive_u32.hpp](../include/supersort/predictive_u32.hpp), instanciación principal `predictive_u32<10,4,2,true>`. El selector opcional vive en [bench.cpp](../bench.cpp); este pseudocódigo describe el kernel, sin atribuirle el comportamiento del selector.

```text
predictivo(A, n):
    si n < 2: devolver
    K = 1024
    media = ceil(n / K)
    capacidad = redondear_abajo_a_multiplo_16(
                    media + floor(4 * sqrt(double(media))) + 31) + 1
    comprobar que K * capacidad es representable
    reservar T[K * capacidad] sin inicializar claves
    count[0..K-1] = 0

    para i = 0 .. n-1:
        x = A[i]
        b = x >> 22
        p = count[b]
        si p == capacidad:
            ordenar A completo con x86-simd-sort
            liberar T y devolver
        T[b * capacidad + p] = x
        count[b] = p + 1

    salida = 0
    para b = 0 .. K-1:
        ordenar exactamente T[b * capacidad : b * capacidad + count[b]]
        copiar esas count[b] claves a A[salida : salida + count[b]]
        salida += count[b]
    liberar T
```

`sqrt(double(media))` y la regla de capacidad son una heurística de coste. No entran en la condición de correctitud: si predicen mal, el chequeo previo a cada escritura activa fallback. La implementación usa memoria/longitudes representables y puede fallar por falta de memoria como otros sorters auxiliares; no promete ordenar arrays que no pueden alojarse. No hay reutilización de scratch entre llamadas.

### Argumento de correctitud

Durante scatter, A permanece idéntico a la entrada. Para cada bucket b, los primeros `count[b]` slots de su región contienen exactamente las apariciones de claves de ese prefijo consumidas hasta ese momento. Los contadores no exceden capacidad porque el chequeo precede a la escritura; las regiones de buckets son disjuntas. Los huecos no se leen ni se pasan a la ordenación local.

Si un bucket se llena, ordenar el A original completo conserva todas las claves, incluidas las todavía no visitadas. El contenido parcial de T se descarta. La exactitud en esa rama depende de la exactitud del sorter upstream, cuya implementación y pruebas se conservan; esta nota no afirma una nueva prueba formal de toda esa biblioteca.

Si termina scatter, los contadores suman n y cada ocurrencia de entrada aparece una vez en T. Ordenar cada tramo válido conserva su multiconjunto y lo deja ascendente. Para b<c, toda clave del bucket b es menor que cualquier clave del bucket c porque sus intervalos numéricos no se solapan y están ordenados por prefijo. Concatenar por b produce por tanto el multiconjunto original en orden global. Valores repetidos pertenecen al mismo bucket y se emiten tantas veces como se almacenaron; 0 y UINT32_MAX son claves normales. No se usan centinelas. Esto prueba el esquema condicionado al sorter local exacto y a reservas válidas, no estabilidad con payload.

### Tiempo y memoria

Sea `m_b=count[b]`, `c=capacidad` y `S(m)` el coste del sorter exacto local. Sin overflow:

`T = O(K + n) + reserva(Kc) + sum_b S(m_b)`.

Para constantes K y Slack, `Kc = O(n + sqrt(nK) + K) = O(n+K)`; para K=1024 fijo es O(n). Con sorter local acotado por O(m log m), la suma es como máximo O(n log n). Con overflow se añade como máximo un prefijo O(n) de scatter y se ordena toda la entrada: peor caso O(n log n), **no O(n)**. El límite de profundidad y fallback de upstream evita presentar un quicksort sin protección como cota garantizada. Una prueba formal de todas las rutas upstream sigue fuera del alcance de esta nota.

Para uniforme independiente, cada `m_b` tiene marginal Binomial(n,1/K). Por linealidad, `E[sum S(m_b)] = K E[S(M)]` sin requerir independencia entre buckets. Sustituir esa expresión por `K*S(n/K)` ignora colas y escalones de redes. Tampoco basta analizar solo la rama de éxito: el tiempo esperado incondicional incluye probabilidad y coste del overflow. No se establece aquí una cota esperada más fuerte ni un modelo probabilístico aplicable a entradas arbitrarias.

Memoria auxiliar de este kernel en ABI de 64 bits: `4Kc + 8K` bytes, más objetos pequeños, metadata del asignador y pila/fallback del sorter. En n=100.000, media98, capacidad161: 659.456 bytes de claves y 8.192 de contadores. No es in-place. En una entrada concentrada falla pronto o cae al fallback, pero la reserva sobrante ya se ha pagado.

Fuera del sorter local, una ejecución completa sin overflow realiza n lecturas de claves de A, n escrituras de claves en T y una copia final de n claves que vuelve a leer T y escribir A: **16n bytes lógicos de claves**, más accesos a contadores e inicialización de metadata. Las referencias de red/partición local añaden trabajo no cuantificado por esa cifra. La variante zeroed añade inicialización lógica de 4Kc bytes; la principal raw no inicializa huecos. En overflow tras k inserciones se han leído k+1 claves y escrito k claves en scratch; se añade el tráfico del sorter completo. No convertir estos conteos en ancho de banda DRAM, misses o ciclos sin contadores o medición apropiada.

Adversarios importantes: prefijos concentrados, outliers que engañan muestreo, pocos valores con gran multiplicidad, hojas cerca de los saltos 128/256 y n que incrementa destinos/capacidad. La seguridad del fallback garantiza exactitud, no rapidez ni una regresión máxima.

## Evidencia reproducible y brechas del objetivo de tamaño

Las implementaciones nativas, orquestadores Python, fuentes fijadas, licencias, hashes, CSV y metadatos están enlazados desde el [índice de experimentos](../results/index.md). El protocolo y sus límites están en [[01 - Contrato experimental]], y las pruebas exactas/sanitizadores por etapa en [[06 - Correctitud y límites]]. Los conteos de salidas no equivalen a arrays independientes. Un benchmark correcto no constituye una prueba exhaustiva sobre todos los arrays posibles.

E001, E003, E005, E007, E012, E017, E020, E022 y E030 ya cubrían 10M. E003 incluye siete familias a ese tamaño. Muchas otras tandas grandes usan solo uniform o uniform/SplitMix. E043 añadió diez familias a 10M para quick128 y tres familias a 100M.

En [E030 Linux](../results/e030_linux_strong/summary.md), 10M, tres semillas17/83/501 y once repeticiones por entrada:

| Distribución | Medianas predict_fixed, rango entre semillas | Medianas mejor referencia externa, rango | ratio mejor referencia / predict_fixed |
|---|---:|---:|---:|
| uniform | 75,917–76,577 ms | vqsort 45,821–46,753 ms | 0,598–0,613 |
| SplitMix | 75,454–77,444 ms | vqsort 45,531–46,677 ms | 0,588–0,619 |

Son seis entradas de una serie, sin mezclar sistemas o tandas. El reparto predictivo pierde aproximadamente 1,62–1,70x en esos casos frente a vqsort; la mejora del nicho de 100k no se extiende a 10M. `adaptive_fixed` a 10M llama directamente a vqsort por su regla de tamaño: una pequeña diferencia de tiempos entre esos nombres no prueba un algoritmo propio mejor en millones.

E043 usó el binario exacto de E040. Quick128 gana 17/20 frente al DSO de control a 10M y 1/20 frente a la mejor referencia de cada entrada. A 100M gana 2/3 y 0/3 respectivamente. E043 recoge RSS de proceso completo. E044 añadió ciclos, instrucciones y fallos genéricos de caché y de rama durante las llamadas a ambas bibliotecas. Sigue pendiente aislar el pico de memoria por algoritmo y el ancho de banda DRAM. Las últimas variantes de mergesort tampoco cubren 10M. [[15 - Escala y contadores]].

Windows/GCC16 y Ubuntu WSL/GCC11 son dos entornos del mismo Ryzen7 5800X; **no son dos arquitecturas CPU**. No hay evidencia en Intel, ARM ni otro presupuesto de registros/caché. Afinidad lógica2 no fija frecuencia/carga ni identifica por sí sola el mismo núcleo físico entre sistemas. No generalizar a AVX-512, multihilo o GPU.

## Novedad y valor de una eventual publicación

El código actual combina mecanismos establecidos: distribución por bits, capacidad sobrante, SIMD y fallback; quick128 cambia un umbral; el árbol ponderado remite a Powersort. Las observaciones negativas y el aislamiento de mecanismos tienen valor metodológico, pero **no sostienen todavía una contribución algorítmica novedosa**. El siguiente diagnóstico debe explicar qué cambia en el trabajo y qué varía aun con los mismos bytes, sin inventar una causa de caché/allocator/ASLR por correlación.

Solo si emerge un mecanismo distinguible de antecedentes y mejora reproducible frente a implementaciones competitivas tendría sentido proponer un artículo de algoritmo. Esquema condicional: problema/contrato y modelo; antecedentes y diferencia concreta; algoritmo e invariantes; cotas y adversarios; implementación; metodología prerregistrada y fuentes exactas; resultados por familia/hardware; costes de observación/memoria; negativos y amenazas a validez. Si la aportación queda en ajuste microarquitectónico, presentarla como estudio de ingeniería de kernels o benchmarking, con ese alcance, sin título que prometa un nuevo paradigma de sorting.

El próximo contraste de mezcla SIMD mantiene fijo el árbol de E038 y cambia cómo se emiten las claves durante cada fusión. [[14 - Diseño de mezcla SIMD]].
