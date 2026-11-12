# Contrato experimental

Inicio: 2026-11-04. Máquina: AMD Ryzen 7 5800X, Windows, GCC 16.1.0 MinGW, Python vía uv.

Primera fase: uint32, orden ascendente, claves sin payload, un hilo, CPU exclusivamente. Después: int32 con signo, otras anchuras, SIMD y varios hilos. No se requiere estabilidad para claves sin payload. La estabilidad será otro contrato si añadimos registros.

La rutina debe devolver el resultado en el vector de entrada. Incluimos reserva e inicialización de memoria auxiliar y copia final dentro del tiempo. Excluimos generación, copia inicial común y comprobación. Memoria auxiliar O(n) permitida, pero debe declararse.

Validación: igualdad exacta con std::sort fuera de la región medida. Orden de algoritmos aleatorio en cada repetición; una ronda previa de calentamiento. Mismos datos para todos, varias semillas y tamaños. Guardar CSV crudo, compilador, flags, hashes de fuentes y dependencias. No ejecutar benchmarks en paralelo. No confundir repeticiones de una misma semilla con entradas independientes.

Casos: uniforme 32 bits, rango denso de 16 bits, 16 claves dispersas, todo igual, ordenado, inverso, mezcla concentrada con outliers. Añadir adversarios y tamaños de frontera antes de promover candidato.

Referencias iniciales: std::sort, pdqsort_branchless, ska_sort, LSD radix 8 bits e histogramas fusionados, LSD radix 11 bits e histogramas fusionados. Nuestros radix NO representan todo el estado del arte. Pendientes: x86-simd-sort/vqsort, IPS4o/IPS2Ra y radix con distribución bufferizada.

Límites: afinidad y frecuencia aún no fijadas; sin contadores hardware; medición caliente tras copia y validación. No inferir bytes DRAM de los recorridos lógicos. No prometer mejora universal ni novedad sin revisión bibliográfica.

Desde E009: afinidad fija a CPU lógica 2 mediante API Windows en el runner; la heredan los procesos de benchmark. Frecuencia y carga de fondo siguen sin control explícito. Desde E018: vqsort (Highway) estático nativo y ska_sort_copy también disponibles. Compilar bibliotecas y candidatos con los mismos flags nativos. No modificar fuentes ni headers mientras esté compilándose el runner: sus snapshots se guardan al completar la compilación. Se puede trabajar en notas durante una medición.

E043 registra RSS máximo y fallos de página del proceso completo. E044 cuenta ciclos, instrucciones y fallos genéricos de caché y de rama en una tanda aparte con las bibliotecas de rendimiento exactas. Estas métricas tienen el alcance y los límites de [[15 - Escala y contadores]]. El contrato de tiempo permanece como se definió arriba.
