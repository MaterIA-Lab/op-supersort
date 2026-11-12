# E043 — alcance hasta 100 millones, mismo ejecutable

2026-11-05. Prerregistro previo a tiempos E043. Medir alcance de escala de quick128 congelado. E042 fue diagnóstico con entradas reutilizadas y no borra regresiones E040/E041. Esta fase usa tamaños y semillas fijados de antemano y no selecciona umbral ni candidato por resultado.

CPU uint32 ascendente, sin payload, un hilo, Ubuntu WSL/AVX2 CPU2. Mismo bench.bin de E040, mismas DSOs, mismas regiones de tiempo y comprobación exacta contra std::sort en cada salida. Reserva y copia final incluidas. Una ronda de calentamiento por proceso y orden de algoritmos barajado por el ejecutable. Sin compilación ni cargas intensivas concurrentes. Fuentes, dependencias, hashes y CSV en carpetas nuevas.

## Matriz principal

- Tamaños100000,1000000,10000000. Semillas60101 y73529. Diez distribuciones uniform,splitmix,sorted,reverse,equal,few,near_sorted,alternating,skew,forced_middle. Equal y alternating repiten datos con ambas semillas.
- Cinco repeticiones medidas más calentamiento. Diez algoritmos E040 en el orden archivado std,stdstable,pdq,simd,vq,power,ips2ra,ips4o,simd256dso,quick128. 60 entradas nominales, 3000 muestras, 3600 salidas exactas previstas. Etiqueta e043_scale_main.

## Matriz de capacidad

- Tamaño100000000. Semilla91573. Distribuciones uniform,few,forced_middle. Tres repeticiones más calentamiento. Siete algoritmos en orden archivado pdq,simd,vq,ips2ra,ips4o,simd256dso,quick128. Se reduce el coste de la tanda más grande y se mantienen referencias competitivas. 63 muestras,84 salidas exactas previstas. Etiqueta e043_scale_100m. No generalizar esta matriz parcial a toda distribución.
- Exigir 4 GiB MemAvailable antes de cada caso 100M. Tres arrays base del ejecutor necesitan 1,2 GB decimales más memoria de algoritmos y proceso. Si falta memoria o falla un proceso, conservar el parcial y documentarlo, sin reemplazar la entrada.

## Métricas e interpretación

Medianas y rango por entrada y algoritmo. Informar ratios control256/candidato, host/candidato y mejor referencia incluida/candidato, con todas las pérdidas. Mostrar 10M/100M por separado. No mezclar factores de distintos protocolos ni convertir victoria local en evidencia de novedad. La muestra de 100M tiene una sola semilla por familia.

`/usr/bin/time` registra RSS máximo, faults y cambios de contexto del proceso completo. Incluye preparación, referencia, copias y todos los algoritmos, por lo que no atribuye memoria a una llamada. Se puede informar tasa de claves/s; no se infiere ancho de banda físico. Probar disponibilidad de contadores hardware fuera de la medición, conservar diagnóstico. Si faltan, indicar huecos. Registrar memoria disponible y plataforma de la serie. No hay segunda arquitectura en este equipo.
