# E036 — contraste de mezcla con hojas SIMD

2026-11-05, registrado antes de ejecutar. Hipótesis M2 de [[07 - Hipótesis CPU quicksort mergesort]].

Principal merge_skip: hojas de 128 claves por x86-simd-sort; mezcla binaria std::merge alternando entrada/scratch; si max(izquierda)<=min(derecha), copia el tramo en vez de mezclar. Control merge_simd: idéntico sin esa comprobación. No se elige entre ellos después. Todo vuelve al array original; reserva de n uint32 sin inicializar y copia final incluidas. CPU, un hilo, sin payload ni promesa de estabilidad. No se introduce una reserva persistente.

Mecanismo: el test puede ahorrar comparaciones y ramas cuando los runs adyacentes ya están globalmente ordenados. El ping-pong exige copiar incluso en ese caso. La aleatoriedad puede pagar el test inútil y la mezcla escalar perder ante quicksort SIMD. Se elige hoja128 por diagnóstico E035; esta selección necesita datos nuevos, no reciclar E034 como validación.

Correctitud Ubuntu: tamaños 0,1,2,31,32,33,63,64,65,127,128,129,255,256,257,511,512,513,1025; quince distribuciones de la matriz, semillas 3109/9103, una repetición y calentamiento; ambos kernels.

Rendimiento Ubuntu: tamaños 65537,100003,262147,1000003; semillas 3109/9103; distribuciones uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted,runs256,runs4096,runs_unequal. Once repeticiones + calentamiento, CPU2. Referencias std,stdstable,pdq,simd,vq,ips2ra,ips4o. Control merge_simd separado de referencias externas.

Criterio: informar principal/control por distribución, todos los negativos, y principal/mejor referencia. Hipótesis apoyada si el test ahorra en sorted/reverse/equal y no causa pérdidas >5% en ninguna entrada uniform/splitmix. Puede fallar: no ajustar ni cambiar el principal. No afirmar mejora de mergesort competitivo por superar solo std::stable_sort; falta Powersort para evaluar adaptación a runs y este candidato ni siquiera detecta runs naturales. Los generadores runs ordenan bloques del mismo multiconjunto MT; no se garantiza que todas las fronteras sean descensos.

### Corrección razonada antes del benchmark de rendimiento

Al revisar el mecanismo durante la compilación de correctitud, sin mirar tiempos de E036, reverse NO debería ahorrar mezclas: ordenar cada hoja ascendente deja las hojas en orden global descendente. Se conserva el criterio original arriba para trazabilidad; reverse se interpreta como control negativo, no como predicción de ahorro. Predicción corregida: ahorro en sorted/equal y sobrecoste pequeño en uniform/splitmix. Ningún cambio de kernel, matriz o candidato. No llamaremos cumplido al criterio original que incluía reverse si los datos no lo sostienen.
