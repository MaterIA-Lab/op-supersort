# E034 — holdout del selector, registrado antes de medir

Fecha: 2026-11-05. CPU uint32 sin payload, un hilo; contrato de memoria y medición sin cambios.

## Hipótesis y decisión fija

E033 motivó K1280 en el extremo alto: las hojas SIMD tienen tamaños discretos. Una media cercana a 128 hace cruzar ese escalón a muchos buckets. K1280 reduce esa probabilidad pero añade destinos, contadores y multiplicación. No se presupone que mejore todo n.

Candidato principal único: adaptive_e034. Conserva muestra de 256 prefijos, rechazo por frecuencia >8, verificación completa de monotonía y rango [65536,131072] del selector anterior. Dentro: K1024 hasta 114688 inclusive y K1280 después. El corte 114688 (112 Ki elementos) es una decisión heurística previa al holdout entre 100k y 130k, NO un óptimo deducido ni ajustado con datos nuevos. Fuera delega en vqsort. Overflow siempre conserva fallback SIMD exacto.

Candidato secundario fijo: predictk1280, para comprobar la generalización del hallazgo E033; no se sustituirá al principal si gana. Referencias: std, pdq, simd, vq y Linux ips2ra/ips4o. adaptive_fixed como control anterior; no cuenta como referencia externa.

## Matriz cerrada

Windows y Ubuntu por separado. Tamaños 68000,98000,114687,114689,129000,131073. Semillas 2027,7907 (nuevas frente a E033). Distribuciones uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted. Once repeticiones + calentamiento, CPU lógica 2, orden aleatorio. Comprobación exacta de cada salida con std::sort, reserva y copia final dentro del tiempo. No compilaciones concurrentes con mediciones.

No promover por promedio global: informar por distribución y plataforma, todas las regresiones y peor caso. Éxito del nicho: principal más rápido que la mejor referencia externa en TODAS las entradas uniform/splitmix del rango, excluyendo 131073 que delega. Robustez secundaria: cuantificar pérdidas en adversarios, sin exigir victorias universales. No cambiar selector después de mirar resultados.

## Mecanismo pendiente

El holdout mide generalización, no causalidad. Medir después ocupaciones reales, proporción >64/>128/>256 y coste de hojas aisladas. No atribuir regresiones a caché, allocator ni redes solo por estos tiempos.
