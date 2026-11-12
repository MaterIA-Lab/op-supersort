# Escala de quick128 y contadores por llamada

2026-11-05. E043 cerró la brecha de tamaño para quick128 en el mismo Ryzen 7 5800X, Ubuntu WSL, AVX2 y un hilo. E044 estudió eventos de hardware en un host separado. Las series tienen distinto protocolo y se conservan por separado.

## E043 — alcance y capacidad

Cada salida de quick128 y las referencias se comprobó exactamente con `std::sort`. El host y las bibliotecas de rendimiento son los de E040, con hashes comprobados antes y después. La matriz principal incluyó dos semillas y diez familias por tamaño. Equal y alternating repiten arrays entre semillas. La matriz de 100M incluyó una semilla y tres familias con siete algoritmos. [Prerregistro](E043%20-%20Prerregistro%20escala.md).

| Claves | Casos nominales | Gana a DSO256 | Gana a SIMD del host | Gana a mejor referencia incluida |
|---:|---:|---:|---:|---:|
| 100.000 | 20 | 17 | 17 | 4 |
| 1.000.000 | 20 | 17 | 16 | 6 |
| 10.000.000 | 20 | 17 | 18 | 1 |
| 100.000.000 | 3 | 2 | 2 | 0 |

En las cuatro entradas uniformes o SplitMix de 10M, quick128 tardó 46,644–47,587 ms. Mejoró al control DSO256 por factores 1,065–1,109 y vqsort conservó la mejor mediana de esas cuatro entradas. En los dos `sorted` de 10M, IPS4o fue unas 17,5–17,9 veces más rápido. La familia `near_sorted` favoreció a pdqsort. La única primera mediana de quick128 a 10M fue `few` semilla60101, por un margen aproximado de 0,5% frente a DSO256. Los intervalos de las repeticiones deben consultarse antes de interpretar ese margen. [Análisis de 100k–10M](../results/e043_scale_main/analysis-scale.md).

| 100M, semilla 91573 | Quick128 mediana | Control256/quick128 | Mejor referencia | Mejor/quick128 |
|---|---:|---:|---|---:|
| Uniforme | 604,556 ms | 1,057 | vqsort | 0,960 |
| Few | 167,699 ms | 0,974 | SIMD del host | 0,915 |
| Forced_middle | 673,369 ms | 1,114 | vqsort | 0,999 |

En 100M uniforme, el candidato procesó unos 165 millones de claves por segundo y vqsort obtuvo la menor mediana. El margen de `forced_middle` contra vqsort es mínimo con tres repeticiones. RSS máximo en 100M fue 1148,9–1149,2 MiB por proceso. La cifra incluye generación, referencia, copias y siete algoritmos. No atribuye memoria individual ni mide el tráfico DRAM. E043 aporta 3063 muestras y 3684 salidas exactas con calentamientos. [Análisis de 100M](../results/e043_scale_100m/analysis-scale.md).

## E044 — trabajo observado por la PMU

El host nuevo enlazó las dos bibliotecas exactas E040. Se contó solo el hilo que ordena en modo usuario. La región incluye bordes de llamada. Generación, copia común y comprobación quedaron fuera. Las 176 llamadas medidas y 16 calentamientos produjeron 192 salidas exactas. Los 88 controles vacíos dieron medianas de 95–107 ciclos y 33 instrucciones. En las 264 filas, el grupo estuvo activo al menos 99% del tiempo habilitado según el kernel invitado. Los resultados son contadores de diagnóstico, sin ranking temporal. [Prerregistro](E044%20-%20Prerregistro%20contadores.md), [medianas y datos](../results/e044_pmu/analysis.md).

En 10M uniforme, las medianas del candidato registraron aproximadamente 6,6% menos ciclos y 11,1% menos fallos genéricos de caché, con 0,14% más instrucciones retiradas y 27,6% más fallos de rama. En `forced_middle` de 10M también bajaron ciclos y fallos de caché pese a subir instrucciones y fallos de rama. En `few` y `equal` de 180013, la mediana de instrucciones fue idéntica entre umbrales. En `few` de 10M las instrucciones casi coincidieron y los ciclos diferían aproximadamente 13%. El número de instrucciones retiradas por sí solo no describe la duración de esas llamadas.

Los eventos genéricos de caché bajo WSL no identifican un nivel físico ni bytes transferidos. Una reducción de misses junto a una de ciclos es una asociación. Cambiar el umbral modifica el código y la trayectoria. El host observador también cambia las condiciones de ejecución. La disponibilidad del grupo no garantiza que se observe todo el tiempo de pared o que el invitado permita interpretar eventos de memoria física. Faltan ancho de banda DRAM y otra arquitectura. [Interfaz Linux de contadores](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).

La escala confirma un ajuste útil de quicksort con alcance limitado y mantiene negativos claros. La siguiente vía separa el coste de elegir un origen de la mezcla escalar y el coste de la red SIMD. El diseño y la prueba del bloque pendiente quedan listos para fijar la matriz antes del primer prototipo. [[14 - Diseño de mezcla SIMD]].
