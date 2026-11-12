# E037 — runs naturales, antes de medir

Fecha: 2026-11-05. Continúa [[07 - Hipótesis CPU quicksort mergesort]]. CPU uint32 sin payload, un hilo Ubuntu/WSL GCC11.4, CPU lógica2. Contrato sin estabilidad prometida; reserva, inicialización necesaria, liberación y copia final incluidas. Comparación exacta con std::sort fuera del tiempo. No ajuste de candidatos con estos resultados.

## Hipótesis y contraste fijo

Principal único **merge_natural**: runs máximos no decrecientes o estrictamente decrecientes que se invierten. Los cortos se extienden a128 (o cola) y se ordenan por SIMD. Control **merge_fixedruns**: hojas fijas128 SIMD. Ambos usan exactamente el mismo template de planificador por parejas, test de límites ordenados, std::merge, scratch ping-pong y copia final; misma reserva de descriptores ceil(n/128), dentro del tiempo. Solo difiere formación de runs y los niveles derivados. Un run único devuelve sin reservar scratch; sí cuenta la reserva de descriptores. Referencia interna anterior merge_skip incluida para distinguir overhead del nuevo planificador, no para sustituir al principal.

Modelo: si hay r runs, mezclar por parejas requiere ceil(log2(r)) pasadas completas; cada una escribe n elementos incluso cuando solo copia. En sorted/equal r=1 y no hay mezcla ni scratch. En reverse con duplicados el descenso estricto puede dividir runs: no se presupone r=1. En random las hojas se parecerán al control pero la detección cuesta trabajo. El árbol por parejas no pondera longitudes: un run enorme puede volver a recorrerse muchas veces. No se cambia simultáneamente el kernel escalar por SIMD.

## Referencia nueva

Powersort upstream https://github.com/sebawild2/powersort, commit **1d078b6be9023e134c4f8f6de88e2406dc681e89**, MIT conservada. Sin modificaciones algorítmicas. algorithms::powersort<uint32_t*> con defaults minRunLen24/COPY_BOTH/ambas direcciones. Objeto nuevo por llamada: resize del buffer y destrucción medidos. Sin COUNT_MERGECOST. Wrapper evita invocar upstream con n<2. Solo Linux por sus supuestos unsigned long64. Las fuentes exactas se copian en cada resultado nuevo y se comprueba ausencia de cambios locales.

## Matriz cerrada

Distribuciones: uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted,runs129,runs256,runs4096,runs_unequal,run_heavy,alternating,plateaus. Nuevos generadores: run_heavy ordena los primeros floor(3n/4) y luego bloques128 del multiconjunto MT; alternating alterna0/UINT32_MAX; plateaus repite17 veces cada clave cíclica0..8. Runs nominales no garantizan fronteras reales: se medirán las detectadas.

Correctitud: tamaños0,1,2,15,16,17,23,24,25,63,64,65,127,128,129,255,256,257,511,512,513,1025,4097; semillas4243/10007; principal/control/power; una repetición y calentamiento. No usar estos tiempos para ranking.

Rendimiento: tamaños73001,123457,300007,1100009; semillas4243/10007; once repeticiones+calentamiento; orden aleatorio. Referencias externas std,stdstable,pdq,simd,vq,power,ips2ra,ips4o. Controles merge_fixedruns y merge_skip. Principal merge_natural. 152 entradas, once algoritmos. Sin cargas intensivas ni compilaciones concurrentes.

Diagnóstico después de todas las repeticiones de cada entrada, FUERA de tiempo: ejecutar copias instrumentadas del mismo template, contar runs iniciales, elementos SIMD/invertidos, niveles, salidas mezcladas/copiadas/copia final. Verificar también estas dos salidas exactamente. No clasificar su tiempo ni confundir movimientos lógicos con DRAM. Estos chequeos extra se contabilizan separados del índice normal.

## Criterios antes de datos

1. Mecanismo: principal más rápido que control en TODAS las entradas sorted/reverse/equal/runs4096; contrastar reducción de niveles/movimientos, no solo tiempos.
2. Sobrecoste: ninguna uniform/splitmix pierde >10% frente al control. Si falla, no ocultarlo con promedio.
3. Competitividad aparte: informar siempre principal/mejor referencia externa y principal/Powersort por entrada/distribución. Ganar al control NO promueve candidato competitivo. No redefinir éxito por superar solo std::stable_sort.
4. Conservar adversario run_heavy, todos los negativos y dispersión. No elegir algoritmo por entrada ni retocar tamaño128/cortes tras observar datos. El holdout de E034 no se reutiliza para validar este candidato.
