# E039 — selección escalar por booleanos

Registrado 2026-11-05 durante validación E038 y ANTES de ver sus resultados de rendimiento. Se ejecutará después de cerrar E038, sin cargas concurrentes. Sigue por petición explícita del usuario de no detener la investigación en cada episodio. CPU uint32 sin payload, un hilo Ubuntu/GCC11.4/CPU2. Sin estabilidad prometida. Reserva/planificación/copyback/liberación dentro del tiempo.

## Hipótesis y candidato fijo

Principal merge_tree_cmov frente a control merge_tree_power de E038: MISMA formación natural128, MISMO plan Powersort exacto, test de límites, capacidades de runs/plan/workspace y scratch y copia de vuelta. Solo cambia el kernel de mezcla: cargar ambas cabeceras, take_left=(l<=r), seleccionar valor con ternario, incrementar i por take_left y j por !take_left; copiar colas al agotarse una fuente. Comparación uint32 directa sin restas con signo ni centinela MAX. Cargar solo después de comprobar ambos límites.

No se elige el árbol ganador de E038 después: ponderado ya fijado aquí. E037 merge_natural es control práctico, no referencia externa ni sustituto del principal. Referencias externas std,stdstable,pdq,simd,vq,power,ips2ra,ips4o.

Modelo: una rama dependiente de valores por salida puede perder con intercalación aleatoria. Selección por cmov/setcc podría evitar fallos de predicción, pero también cargar cabeceras repetidamente y crear cadenas de dependencias en índices; no garantizar velocidad. En tramos desbalanceados/duplicados/predecibles puede ser peor. Alternancia perfecta no se considera por sí sola impredecible.

Inspeccionar y archivar ensamblado del BINARIO EXACTO de medición. Si el compilador conserva rama de selección, no afirmar que se validó eliminación de mispredicciones ni modificar flags/kernel después para rescatarlo. La ausencia de rama de datos tampoco prueba ciclos o fallos hardware; no hay contadores hardware.

## Matriz cerrada nueva

Rendimiento tamaños160001,330017,650011,1300021; semillas9011,29009; once repeticiones+calentamiento, orden aleatorio, once algoritmos. Distribuciones22 de E038: uniform,splitmix,dense16,few,equal,sorted,reverse,skew,sampletrap,samplemiss,prefixcluster,near_sorted,runs129,runs256,runs4096,runs_unequal,run_heavy,alternating,plateaus,forced_front,forced_middle,forced_tail. 176 casos nominales; como máximo164 datasets distintos por duplicación de semillas en equal/alternating/plateaus. No reciclar tamaños/semillas de E038 para validar el kernel.

Correctitud: tamaños0,1,2,15,16,17,23,24,25,63,64,65,127,128,129,255,256,257,511,512,513,1025,4097,131073; mismas22 distribuciones y semillas9011/29009; principal/control/power, una ronda+calentamiento. Estos tiempos NO se usan como ranking. Sanitizadores/guardas antes del benchmark, separados.

Diagnóstico fuera de tiempo: ejecutar los mismos dos candidatos instrumentados, verificar salidas exactas y exigir runs/hash/plan/C_tree/C_exec/copyback idénticos. Solo kernel cambia; si contadores no coinciden, investigar y no promover. No interpretar los tiempos instrumentados como benchmark. Dos verificaciones extra por caso, aparte del índice.

## Criterios antes de datos

1. Mecanismo: ensamblado sin rama de selección dependiente de la comparación de claves; ramas de loop/agotamiento permitidas. Declarar claramente si se consiguió o no, sin asumirlo por C++.
2. Rendimiento: principal gana a control en TODAS las16 entradas nominales uniform/SplitMix. Si no, falla criterio estricto, sin compensar con promedio.
3. Robustez: ninguna entrada de dense16/few/equal/skew/forced_front/forced_middle/forced_tail pierde>10% frente al control. Conservar todos los negativos incluso si mejora random.
4. Informar siempre frente a E037, Powersort y mejor referencia externa. No promover sorter general solo por ganar al control. No cambiar principal/flags/política retrospectivamente.
