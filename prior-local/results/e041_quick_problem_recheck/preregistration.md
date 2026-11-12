# E041 — confirmar quick128 sin recompilar

Registrado 2026-11-05 tras cerrar tiemposE040 y antes de nuevos datos. Candidato fijo quick128 y control simd256dso, más simdhost y todas las referenciasE040. No retocar umbral128, pivotes, casos o flags. CPU uint32 sin payload/un hilo/Ubuntu CPU2. No otra carga intensiva.

## Por qué otro holdout

E040 gana16/16 random frente al control y host, pero falla robustez>10% en8193/skew/33013. No declararlo universal ni borrar ese negativo. Nueva matriz independiente valida generalización; diagnóstico separado repetirá el problema para observar persistencia sin elegir ganador retrospectivamente.

Usar EXACTAMENTE results/e040_quick_holdout_linux/bench.bin y sus DSOs originales enlazados. Verificar sha256 de ejecutable, bibliotecas y snapshots antes/después; no compilar ni cambiar fuente usada. Guardar nuevo UTC/entorno, fuente original/privada/licencias, argumentos y CSV nuevos. run_existing.py orquesta, afinidadCPU2 y subprocess nuevo por entrada igual que run.py. Warmup y orden aleatorio nativos conservados. Reserva y copias requeridas dentro; generación/copia común/comprobación exacta fuera.

## Matriz principal cerrada

Tamaños8209,180013,1500007; semillas14009,41011,58013 nuevas; distribuciones22 de E040; once repeticiones+calentamiento.198 nominales, como máximo180 datasets distintos (equal/alternating/plateaus ignoran semilla). Diez algoritmos sin sustituciones: std,stdstable,pdq,simd,vq,power,ips2ra,ips4o,simd256dso,quick128. Etiqueta e041_quick_holdout_exact.

Criterios: (1) quick128 gana TODAS las18 entradas uniform/SplitMix frente a simd256dso Y simdhost; (2) ninguna dense16/few/equal/sorted/reverse/skew/alternating/plateaus pierde>10% frente al control; (3) informar mejor referencia y todas las pérdidas. Un fallo no se rescata por medias ni con parámetros nuevos. Incluso si pasa, alcance solo este uint32/AVX2/entorno, sin superioridad universal ni novedad.

## Diagnóstico registrado, separado

Después del principal, n8193, semillas12007/33013 de E040, distribuciones skew/uniform/dense16,51 repeticiones+warmup, mismos10algoritmos/mismoejecutable. Etiqueta e041_quick_problem_recheck. No es holdout independiente ni se suma a los criterios principales. Conservar resultado inicial aunque no se reproduzca; no atribuir causa a ruido/allocator/layout sin aislamiento. No elegir semillas favorables ni hacer más reintentos según este resultado.

No se repiten sanitizadores porque no cambia ningún byte nativo; E040 conserva6624 casos con ASan/UBSan y guardas. Los tamaños/semillas nuevos se verifican exactamente en cada salida nativa contra std::sort.
