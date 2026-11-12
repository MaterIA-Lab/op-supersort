# E056 — Confirmación con las tres referencias

El filtro previo dio 1,251360× y 1,260967× frente a vqsort en `mixed`. El margen sobre 1,25× es pequeño. Se repetirá la comparación con las tres referencias fijadas de E054 en la misma tanda, antes de evaluar una integración. [Filtro](../results/e056_binary_filter/summary.md).

Se conservan los mismos kernels, tamaños, generadores, semillas, costes y controles de E056. Se añaden las semillas `53309` y `78041` en `mixed`, fijadas antes de medir la confirmación. Se prueban `binary`, `split`, vqsort estático nativo, x86-simd-sort estático nativo e IPS2Ra secuencial. Un calentamiento, siete muestras por caso y brazo y un hilo fijado a CPU lógica 2. El estado inicial de pivotes de vqsort sigue emparejado en cada ronda.

La confirmación exige ruta de ventana en ambos candidatos, mejora estricta sobre E049 y `min(mediana(vq), mediana(simd), mediana(ips2ra))/mediana(binary) ≥ 1,25` en cada una de las cuatro entradas `mixed`. Si alguna falla, se publican sus tiempos y se aplaza la integración. Los cuatro controles se mantienen en ambas semillas originales y se publican completos. La comparación se limita al candidato autónomo y su probe cobrado.
