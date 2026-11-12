# E035 — ocupación y hojas aisladas

Registrado 2026-11-05 antes de ejecutar. Diagnóstico, sin candidato ganador ni cambio del selector E034.

Dos observables separados: ocupación real de K1024/K1280 usando exactamente generadores MT/SplitMix de E034, tamaños y semillas de E034; coste aislado de qsort SIMD para longitudes 31/32/33/63/64/65/95/96/97/111/112/113/127/128/129/159/160/161/255/256/257. Datos uniformes, 512 hojas independientes, 15 repeticiones más calentamiento, CPU2. Copia inicial fuera del tiempo, comprobación exacta de cada hoja contra std::sort fuera. No es un sorter completo: no incluye scatter, reserva ni copia final global, y sus tiempos NO se clasifican junto a E034. Buffers de microbenchmark se reservan antes de medir por diseño; es otro contrato de medición.

Predicción: aumentar K cerca de 129k reduce mucho los buckets >128; si las hojas de 129 cuestan más que las de 128, resulta compatible con la hipótesis. No prueba causalidad del rendimiento total: faltan layout, coste de scatter y llamadas intercaladas reales. No ajustar K ni corte con esta serie y presentar validación reutilizando E034.
