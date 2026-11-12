# E040 — umbral de hojas quicksort 256→128

Registrado 2026-11-05 mientras se mide E039, sin esperar sus resultados. Se ejecutará después, en CPU Ryzen5800X AVX2, uint32 sin payload/un hilo/Ubuntu GCC11.4/CPU2. Reserva interna/fallback/copia requerida dentro del tiempo; orden aleatorio, calentamiento y comprobación exacta fuera. No se reclama novedad. Sigue la petición de encadenar investigación, no parar en cada episodio.

## Hipótesis y contraste fijo

E035 observó un salto grande de coste128→129 en hojas. Principal quick128: copia privada del x86-simd-sort fijado6e059b14975df2e3c74260ec905167a1be5a34ca, modificando SOLO network_sort_threshold256→128 en avx2_vector<uint32_t>. Mantener pivote, partición, duplicados, límite max_iters y fallback. No usar XSS_MINIMAL_NETWORK_SORT (bajaría a8 y cambiaría demasiado). No modificar vendor original ni tipos int32/float.

Control simd256dso: mismo upstream sin cambios algorítmicos. Ambos se compilan como bibliotecas compartidas separadas con mismos flags nativos, PIC, visibilidad oculta y mapa que exporta solo wrapper propio. Evita ODR/interposición entre dos versiones de templates. Verificar exportaciones y archivar bibliotecas/binario/hashes/fuentes/licencias. También comparar referencia simd original del host para exponer posible coste del wrapper/DSO; no elegir baseline favorable después.

Hipótesis: una partición adicional seguida de hojas<=128 puede costar menos que la red grande129–256. Puede fallar por coste de pivote/partición, ramas, movimientos y recursión. Tráfico vectorial de pila y tamaño de código se inspeccionarán en ensamblado; no asumir spills por contar variables ni atribuir todos los ciclos sin perfil. No cambiar flags/umbral después de ver datos. Si no hay símbolos separables de redes, declarar ese límite y no inferir ausencia de tráfico de pila.

## Matriz cerrada

Rendimiento tamaños8193,65539,250013,1000033; semillas12007,33013 nuevas; once repeticiones+calentamiento; distribuciones22 de E038/E039 (uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted,runs129,runs256,runs4096,runs_unequal,run_heavy,alternating,plateaus,forced_front,forced_middle,forced_tail). 176 casos nominales, como máximo164 datasets distintos. Algoritmos std,stdstable,pdq,simd,vq,power,ips2ra,ips4o,simd256dso,quick128. Control causal simd256dso, referencias externas incluyen también el simd original del host.

Correctitud: tamaños0,1,2,15,16,17,23,24,25,63,64,65,127,128,129,255,256,257,511,512,513,1025,4097,131073; mismas22 distribuciones y semillas; quick128/simd256dso/simd, una ronda+calentamiento. Esos tiempos no se usan como ranking. Guardas/ASan/UBSan de ambos DSOs antes de rendimiento, sin otras cargas concurrentes.

Este contraste mide sorter COMPLETO. No se rescatará por una victoria aislada de microkernel. E035 es motivación previa, no validación de quick128. No se afirmará haber contado hojas/particiones si solo se inspecciona ensamblado estático; la instrumentación dinámica del upstream queda pendiente si el resultado merece más investigación.

## Criterios

1. Aislamiento: modificación algorítmica única exacta, static_assert del umbral, API AVX2 y exportaciones limitadas. Guardar fuente original y privada y delta.
2. Rendimiento: quick128 gana a simd256dso en TODAS las16 entradas uniform/SplitMix. Cualquier pérdida falla criterio estricto; no elegir tamaños/semillas a posteriori.
3. Robustez: ninguna dense16/few/equal/sorted/reverse/skew/alternating/plateaus pierde>10% frente al control. Informar todas las demás pérdidas también.
4. Comparar SIEMPRE con simd host y mejor referencia completa. Si solo mejora baseline privado pero no host, no ocultarlo ni afirmar mejora robusta del upstream. No seleccionar ganador por entrada ni retocar umbral tras medir.
