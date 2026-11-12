# Diagnosticar variabilidad antes de adaptar

2026-11-05, propuesta original tras E038–E041. El diagnóstico posterior se registró en [[E042 - Prerregistro trabajo y procesos]] y se cerró en [[13 - E042 trabajo y variación]]. No retocar quick128 ni escoger semillas según los resultados. Ver [[09 - Lecciones árbol ramas y hojas]].

## Evidencia que motiva el diagnóstico

E040 quick128 gana16/16 random frente a control y host. E041 con MISMO binario/DSOs gana17/18, pero SplitMix180013/14009 pierde contra ambos; few180013/58013 también supera el límite de regresión. Además algunas forced tienen pérdidas grandes, visibles en tabla aunque no fueran parte del criterio de robustez. No promover universalmente.

El problema original8193/skew/33013 de E040 (control/candidato0.898) pasa a1.121 en el único recheck registrado, con51 repeticiones, sin recompilar ni cambiar código. El resultado previo permanece. Recompilar no es condición necesaria para que cambien esos tiempos; esto NO prueba que la causa sea ruido, allocator, ASLR o caché. Cambian proceso y entorno de ejecución; igualdad de bytes no garantiza igualdad de direcciones/estado.

## Dos explicaciones que deben separarse

1. Coste algorítmico de datos: umbral128 añade particiones; pivotes, duplicados o fallback pueden producir trayectorias desfavorables en algunos datos. Medir número/tamaño de particiones, hojas por bandas, detección Sorted/Only2Values, llamadas a std::sort y elementos del fallback.
2. Variación de ejecución: direcciones, stack/código, page faults, frecuencia/carga y orden caliente. No basta contar malloc/free ni atribuirlo a layout por observar una anomalía. Capturar direcciones relevantes y condiciones sin mezclar tiempos instrumentados con clasificación.

## Contraste que conviene registrar después

Crear copias instrumentadas SEPARADAS del upstream original/candidato, partiendo de fuentes E040 exactas. Contadores fuera del ranking, salidas verificadas con std::sort. Mantener intactos los binarios de rendimiento. Repetir un conjunto fijado que incluya fallos y controles positivos nuevos, sin probar semillas hasta que salga el resultado deseado.

Registrar todas las rondas/procesos antes de medir, separar dataset de repetición y conservar su orden. Medir las mismas entradas en procesos nuevos frente a varias rondas del mismo proceso podría ayudar a aislar estado de proceso, sin declarar de antemano ASLR como causa. Instrumentación altera código: usar cuentas de trabajo para mecanismo, no sus tiempos como victoria.

No introducir selector por tamaño/distribución para esconder los fallos antes de entender coste y coste de observar. No barrer umbrales192/224/etc y llamar validación al mínimo. Si se elige otra hipótesis, preregistrarla y usar nuevos datos; todas las series anteriores siguen válidas en su alcance.

## Después del diagnóstico

Si el ahorro del nuevo umbral es robusto en un alcance acotado, validarlo en otro entorno/hardware y luego estudiar integración en hojas de SuperSort. No heredar automáticamente victorias de quick128 a buckets: cambia su distribución de tamaños y el coste de llamadas. Para mergesort, la próxima vía con más margen sigue siendo procesar varias claves por decisión (SIMD), con invariante/correctitud fijados antes del benchmark, no otro ternario escalar.
