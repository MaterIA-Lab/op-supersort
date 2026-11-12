# Estado actual de SuperSort

Cierre del 2026-11-05, tras E042–E044 y una sesión de análisis en papel. E044 sigue siendo el último experimento ejecutado. Las estrategias priorizadas están en [[21 - Decisión tras el análisis]].

## Resultados más recientes

- E042 observó más particiones y hojas pequeñas, sin fallback en doce entradas. Hay cambios de ganador entre bloques del mismo proceso y en rutas sin hojas. Las seis pérdidas fuertes de E040/E041 no reaparecieron como medianas de proceso. Se conservan esos negativos y la causa sigue abierta. [[13 - E042 trabajo y variación]].
- E043 cubrió 100k, 1M, 10M y tres casos a 100M. A 10M quick128 gana 17/20 ante DSO256 y 1/20 ante mejor referencia. A 100M gana 2/3 y 0/3 respectivamente. En 100M uniforme tarda 604,556ms, detrás de vqsort. RSS de los procesos de 100M aproximadamente 1,12GiB. [[15 - Escala y contadores]].
- E044 contó ciclos, instrucciones y fallos genéricos de caché y de rama en las llamadas exactas a las bibliotecas. En 10M uniforme, quick128 redujo ciclos y fallos de caché y aumentó instrucciones y fallos de rama. La causa de las pérdidas históricas sigue abierta. [[15 - Escala y contadores]].

## Mejora práctica nueva de quicksort, con excepciones

`quick128` cambia solo el umbral de red AVX2 uint32 de256 a128 en una copia privada del x86-simd-sort original. Pivotes, partición, iguales, profundidad y fallback permanecen intactos. DSOs de control256/candidato128 aislados y flags idénticas; vendor original sin cambios. No se integró por defecto en el selector de buckets.

| Evidencia | Comparación | Resultado |
|---|---|---|
| E040, Linux/AVX2 | 16 uniform/SplitMix contra DSO256 y simdhost | Gana16/16; frente al host1.078–1.120x |
| E040 | mejor referencia externa incluida | Gana53/176 nominales; no general |
| E040 | robustez | Falla8193/skew/33013, ~11.3% más lento |
| E041, mismo binario/DSOs y datos nuevos | uniform/SplitMix contra ambos SIMD | Gana17/18; falla180013/SplitMix/14009 |
| E041 | robustez y referencias | Falla180013/few/58013; gana66/198 ante mejor referencia |

Se conserva como candidato experimental, **no reemplazo universal**. No hay novedad ni superioridad general demostrada. Nuevos arrays y misma compilación no eliminan variación de ejecución: el recheck preregistrado del problema inicial pasa de perder a ganar sin recompilar. Ambos resultados permanecen y la causa está pendiente.

[Análisis E040](../results/e040_quick_holdout_linux/analysis-quick.md), [holdout E041](../results/e041_quick_holdout_exact/analysis-quick.md), [recheck separado](../results/e041_quick_problem_recheck/analysis-quick.md). No mezclar las tres series ni contar el recheck como validación independiente.

## Mecanismos comprobados y límites

- E038: política Powersort ponderada frente a parejas, mismo ejecutor escalar. Predicción de volumen exacta; mejora1.279–1.554x en16/16 forced_front/middle y pasa límite random. Solo2/176 ante mejor referencia.
- E039: selección cmov/setcc confirmada por ASM. Random mejora apenas0.9–2.8%; few hasta3.89x más lento, robustez falla. No cambiar globalmente ni salvar con tabla retrospectiva de selección. En equal no se llama al kernel: no atribuir esas diferencias al cmov.
- E040: ASM de red ascendente32vectores30487bytes/1173 referencias vectoriales estáticas a rsp; red16vectores9993bytes/125 referencias. Compatible con menor código/tráfico de pila, no medida de spills dinámicos, ciclos o DRAM. No se han contado hojas/particiones dinámicas.

[[09 - Lecciones árbol ramas y hojas]] explica por qué menos pasadas, menos ramas o menos variables no garantizan por sí solas acelerar el sorter completo.

## Hallazgo previo de buckets, separado

Prototipo exacto con capacidad prevista y fallback seguro, memoria auxiliar O(n), sin payload/estabilidad. E030 a100k en Ubuntu gana1.233–1.323x; E033 a100k gana1.370–1.387x, en otra serie. E034 selector fijo gana19/20 uniformes del rango en cada sistema, falla el criterio estricto. No hay victoria sostenida en millones ni explicación causal de regresiones E026. No trasladar automáticamente quick128 a sus hojas: sería otro candidato.

## Evidencia y alcance

[Índice](../results/index.md) con **279.065 muestras de tiempo y 319.280 salidas completas exactas con std::sort**, incluyendo calentamientos. Diagnósticos y sanitizadores aparte. Las repeticiones y las semillas de equal, alternating y plateaus no equivalen a entradas independientes.

Fuentes exactas, dependencias, licencias, flags, entorno, CSV, binarios y ensamblados quedan archivados. CPU uint32 sin payload, un hilo; reserva/copia final dentro. Últimas etapas solo Ubuntu/AVX2. No afirmar estabilidad, otro ancho, payload ni otro hardware. Frecuencia, carga y direcciones no completamente controladas.

El siguiente objetivo es un sorter general para aleatoriedad de distintas distribuciones. La hoja de celdas locales queda como pista abierta. La reparación dispersa se conserva para el nicho casi ordenado. No hay tiempos nuevos para ninguna. [[22 - Relevo para un sorter general]], [[20 - Diseño de celdas ordenadas]].
