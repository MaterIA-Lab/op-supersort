# E042 — trabajo algorítmico y variación entre procesos

Registrado el 2026-11-05 antes de compilar o medir esta etapa. Diagnóstico, no nuevo candidato ni holdout de rendimiento. Conserva los negativos E040/E041. CPU uint32, claves sin payload, un hilo, Linux/AVX2, CPU lógica2; ninguna carga intensiva simultánea. Python3 de Ubuntu orquesta (uv no está instalado allí).

## Preguntas cerradas

1. ¿Qué cambian umbral256 y128 en llamadas, profundidad, particiones y volumen lógico, histogramas de hojas, detección Sorted/Only2Values y fallback std::sort? ¿Hay fallback en los fallos conocidos?
2. Con ejecutable/DSOs E040 idénticos, ¿la mediana cambia entre procesos y entre bloques de rondas del mismo proceso? Trabajo constante y tiempos variables descartan una explicación exclusivamente por cambio de trayectoria, pero no identifican frecuencia, ASLR, caché o asignador.

No barrer umbrales, añadir selector, elegir semillas ni prolongar repeticiones tras ver resultados. No convertir los tiempos instrumentados en ranking.

## Matriz cerrada de diagnóstico

Doce entradas, todas reutilizadas: (8193,skew,33013), (8193,uniform,33013), (180013,splitmix,14009), (180013,few,58013), (8209,forced_middle,58013), (8209,forced_tail,41011), (8209,forced_front,58013), (180013,uniform,41011), (1500007,splitmix,58013), (180013,equal,14009), (180013,sorted,14009), (180013,alternating,14009).

Los tres forced son los negativos más fuertes de cada familia en E041: selección deliberada para diagnóstico, nunca validación independiente. Equal/alternating no dependen de semilla.

### Parte A: copias instrumentadas separadas

Partir de los árboles privados exactos src256/src128 archivados en E040. Verificar hashes contra preparación original. Añadir únicamente observación al cuerpo qsort_ (no qselect), en ambos con idéntico parche; APIs C distintas y símbolos internos ocultos mediante mapa de exportación. Vendor y binarios originales intactos. Compilar serialmente O3 y después O1 ASan/UBSan en carpetas nuevas; archivar fuente, parche, flags, licencias, exportaciones y hashes. El contador no es modelo de ciclos/DRAM.

Generador extraído byte por byte de bench.cpp E040; comparar su hash y cada salida con std::sort. Tres ejecuciones nuevas por entrada y umbral, offsets0/1/7 con guardas antes/después. Guardar cada observación; exigir cuentas reproducibles para el mismo dataset/umbral. Añadir validación ASan/UBSan con tamaños0,1,2,7,8,9,15,16,17,31,32,33,63,64,65,127,128,129,255,256,257,511,512,513,8193,8209,65539,180013; las22distribucionesE040; semillas12007/33013; offsets0/1/7. Todas las salidas contra std::sort y guardas; también ejecutar las doce entradas principales bajo sanitizadores.

Contar nodos/elementos por entrada, máximo nivel real (raíz0), hojas por bandas1–8/9–16/17–32/33–64/65–128/129–256, elementos y llamadas de partición, salidas Sorted/Only2Values, llamadas/elementos fallback y extremos iguales omitidos. Control de contabilidad nodos=hojas+fallback+Sorted+particiones; Only2Values es subconjunto de particiones. Profundidad y cuentas describen este código instrumentado, no prueba directa de igualdad de ejecución del original.

### Parte B: tiempos del ejecutable exacto

Después de terminar compilaciones y sanitizadores: ocho procesos nuevos por entrada,31repeticiones+warmup, diez algoritmosE040 y su orden aleatorio nativo sin cambios. Orden de las doce entradas barajado en cada tanda con Python random.Random(420042). Fuente de rendimiento: results/e040_quick_holdout_linux/bench.bin y las mismas rutas deDSOs queE041. Verificar hashes antes/después; ninguna recompilación de rendimiento. Total previsto29760muestras,30720salidas exactas contando warmup.

Observador Python enCPU0, hijo por taskset enCPU2. Una captura temprana de /proc/PID/maps al cargar ejecutable/DSOs, con límite0.25s; conservar mapa y estado incluso si falla. No son direcciones de cada vector ni stack frame. Captura pequeña puede perturbar y no se usa para establecer causalidad. wait4 recoge RSS máximo, faults y cambios de contexto por proceso completo, incluyendo generación/comprobación. No son métricas de región ordenada. Registrar entorno, afinidad, ASLR/perf_event_paranoid y frecuencia si expuesta; no afirmar control de frecuencia.

Informar por entrada todos los ratios DSO256/quick128 y host/quick128 por proceso, rango de medianas, número de victorias y contraste prefijado bloques0–14/15–30. No agrupar rondas como datasets independientes ni elegir bloque favorable. Una oscilación no borra el resultado anterior. Sin criterio de promoción: conclusión posible es mecanismo parcial, variación observada o diagnóstico inconcluso.

## Cierre previsto

Actualizar diario, reanudar, estado y mapa; análisis completo con negativos. Si aparece una causa no aislada, formular contraste posterior antes de medirlo. Literatura y síntesis del reto acompañan esta etapa; ninguna afirmación de novedad o superioridad universal.
