# E038 — política del árbol aislada

Registrado 2026-11-05 antes de compilar/medir. [[08 - Árbol de mezclas y movimientos]]. CPU, un hilo, uint32 sin payload/estabilidad prometida, Ubuntu WSL/GCC11.4, CPU lógica2. Fuentes/dependencias fijadas como E037. Sin cargas intensivas simultáneas.

## Decisión fija y memoria

Principal único merge_tree_power: política Powersort con poder exacto definido por puntos medios diádicos, stack creciente y fusiones adyacentes. Control merge_tree_pair: árbol binario por parejas. Ambos forman los mismos runs naturales con extensión128 SIMD, reservan las mismas capacidades de runs/plan/workspace y ejecutan el MISMO kernel compartido noinline: si fronteras ordenadas omitir fusión; si no, std::merge a scratch[lo:hi] y copyback a entrada. Siempre queda en la entrada. E037 merge_natural como control práctico, no como referencia externa ni sustituto del principal.

No es invención: política con antecedentes Powersort. No se cambia el upstream que sirve como referencia; nuestro poder usa división binaria exacta en lugar del clz aproximado de su default. Dominio declarado n<=SIZE_MAX/2 para poder duplicar puntos medios sin overflow. n<2 devuelve sin reservas. Si hay un solo run se omiten plan y scratch efectivos, aunque los tres vectores ya han reservado capacidad.

Para cap=ceil(n/128): capacidad de runs16*cap, plan24*(cap-1), workspace16*cap bytes en este ABI, más4n scratch si hay varias runs. Todas reservas, inicialización necesaria, planificación, copias y liberación dentro del tiempo. Son estructuras O(n) distintas de E037, por eso el contraste causal se hace entre los nuevos principal/control.

## Generadores y modelo estructural PREVIO

forced_front/middle/tail: mismo corpus MT por tamaño/semilla. Crear un bloque big=floor(3n/4) y256 bloques pequeños que reparten el resto; ordenar cada bloque y sustituir sus extremos por0/UINT32_MAX; luego ROTAR bloques completos para mover big a posición0/128/256. No sustituir extremos tras rotar: mismo multiconjunto en los tres casos. Todas las fronteras son MAX>0, así que257 runs exactos y ninguna fusión puede omitirse. Para tamaños pequeños de correctitud usar min(256,floor(n/512)) bloques pequeños; si ninguno, un bloque único. En rendimiento todos los pequeños son>=128.

Análisis de longitudes Python sin timing, anterior al experimento:

| n | C_tree pair front/middle | C_tree power front | power middle | pair=power tail |
|---:|---:|---:|---:|---:|
|140009|1258993|420033|507503|420033|
|270011|2427995|810035|978751|810035|
|530017|4766017|1590057|1921265|1590057|
|1200011|10790731|3600035|4350027|3600035|

Profundidad grande: front9→1, middle9→2, tail1→1. Tail es control negativo: NO se exige victoria allí. C_exec=C_tree en estos forzados. Reducir volumen puede no reducir tiempo en igual proporción: planificación, ramas y localidad no están aisladas por contadores hardware.

## Matriz cerrada

Rendimiento: tamaños140009,270011,530017,1200011; semillas6029,18013 nuevas; once repeticiones+calentamiento; orden aleatorio. Distribuciones uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted,runs129,runs256,runs4096,runs_unequal,run_heavy,alternating,plateaus,forced_front,forced_middle,forced_tail (22). 176 casos nominales, como máximo164 datasets distintos porque equal/alternating/plateaus ignoran semilla. Referencias std,stdstable,pdq,simd,vq,power,ips2ra,ips4o; controles merge_tree_pair,merge_natural; principal merge_tree_power. No escoger variante por entrada.

Correctitud: tamaños0,1,2,15,16,17,23,24,25,63,64,65,127,128,129,255,256,257,511,512,513,1025,4097,131073; mismas22 distribuciones y semillas; principal/control/power, una ronda+calentamiento. Tiempos NO se usan para ranking. Sanitizadores/guardas se ejecutarán separadamente antes del benchmark.

Diagnóstico FUERA de tiempo, posterior a todas repeticiones de cada caso: principal/control instrumentados, verificados exactamente, runs/hash de fronteras, elementos SIMD/invertidos, operaciones, C_tree/C_exec/copyback/omitidas. Exigir formación idéntica, r-1 operaciones y copyback=C_exec. No confundir tráfico lógico16*C_exec con DRAM. Sus dos verificaciones por caso se cuentan aparte.

## Criterios

1. Mecanismo estructural: valores forzados de la tabla exactos, front/middle menos C_tree y C_exec, tail iguales. Si no, detener promoción y buscar fallo de modelo/código conservando evidencia.
2. Rendimiento del mecanismo: principal gana a control en TODAS las front/middle. No exigirlo en tail.
3. Sobrecoste: ninguna uniform/splitmix pierde>10% frente al control. No compensar pérdidas con promedios.
4. Informar siempre frente al E037 práctico, Powersort y mejor referencia externa. Éxito causal frente al control no significa sorter competitivo. Conservar run_heavy, todos los negativos, dispersión y semillas, sin retocar política ni kernel.
