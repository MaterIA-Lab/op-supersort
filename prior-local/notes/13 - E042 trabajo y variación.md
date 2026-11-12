# E042 — trabajo de quicksort y variación de tiempos

2026-11-05. En las doce entradas examinadas, las copias instrumentadas nunca activaron el fallback a `std::sort`. En nueve, quick128 reemplazó hojas grandes por más particiones y hojas pequeñas. En `few`, `equal` y `alternating`, los dos umbrales registraron el mismo trabajo y no ejecutaron redes de hoja. Aun así hubo cambios de ganador entre bloques del mismo proceso. [Prerregistro de E042](../results/e042_process_variation/preregistration.md).

## Qué cambia al bajar el umbral

E042-A comprobó 216 salidas exactas con `std::sort` y guardas. Para cada combinación de entrada y umbral coincidieron todas las cuentas y el hash de trayectoria en los tres procesos y los offsets 0, 1 y 7. Se extrajo el generador de E040 y se instrumentaron copias separadas de los dos árboles de fuentes. [CSV de trabajo](../results/e042_work_diagnostic/work.csv), [metadatos](../results/e042_work_diagnostic/metadata.json).

Cada par de la tabla va de umbral256 a umbral128. El porcentaje expresa el cambio de la suma de longitudes de subarrays entregados al particionador. Una clave que pasa por varias particiones suma una vez en cada una.

| n | Distribución | Semilla | Particiones | Elementos en particiones | Hojas | Hojas 129–256 | Profundidad máxima |
|---:|---|---:|---:|---:|---:|---:|---:|
| 8193 | skew | 33013 | 45 → 94 | 45.630 → 54.465 (+19,36%) | 46 → 95 | 41 → 0 | 7 → 8 |
| 8193 | uniform | 33013 | 47 → 96 | 46.158 → 54.631 (+18,36%) | 48 → 97 | 43 → 0 | 7 → 8 |
| 180013 | splitmix | 14009 | 1033 → 2061 | 1.837.127 → 2.019.783 (+9,94%) | 1034 → 2062 | 895 → 0 | 12 → 14 |
| 180013 | few | 58013 | 15 → 15 | 754.095 → 754.095 | 0 → 0 | 0 → 0 | 6 → 6 |
| 8209 | forced_middle | 58013 | 50 → 97 | 50.549 → 58.758 (+16,24%) | 51 → 98 | 37 → 0 | 9 → 10 |
| 8209 | forced_tail | 41011 | 49 → 102 | 49.701 → 58.864 (+18,44%) | 50 → 103 | 41 → 0 | 9 → 10 |
| 8209 | forced_front | 58013 | 49 → 97 | 50.312 → 58.793 (+16,86%) | 50 → 98 | 37 → 0 | 8 → 10 |
| 180013 | uniform | 41011 | 1028 → 2058 | 1.825.939 → 2.009.466 (+10,05%) | 1029 → 2059 | 891 → 0 | 12 → 13 |
| 1500007 | splitmix | 58013 | 8613 → 17172 | 20.034.144 → 21.556.984 (+7,60%) | 8614 → 17173 | 7462 → 0 | 17 → 18 |
| 180013 | equal | 14009 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| 180013 | sorted | 14009 | 1078 → 2179 | 1.913.605 → 2.110.506 (+10,29%) | 1079 → 2180 | 815 → 0 | 15 → 16 |
| 180013 | alternating | 14009 | 1 → 1 | 180.013 → 180.013 | 0 → 0 | 0 → 0 | 1 → 1 |

En las nueve entradas que llegan a las redes, los elementos adicionales en particiones equivalen a entre 1,000 y 1,116 veces n. La suma de tamaños de las hojas sigue siendo n en los dos umbrales. Por ejemplo, en `skew` de 8193 las 46 hojas de 256 se reparten en 5 de 65–128 y 41 de 129–256. Las 95 hojas de 128 se reparten en 14 de 33–64 y 81 de 65–128. La reducción de tamaño de hoja exige trabajo extra de partición, tal como anticipaba E040. La cuenta no estima por sí sola qué parte de ese coste se compensa con redes más pequeñas. [Histograma y elementos por banda](../results/e042_work_diagnostic/work.csv), [análisis de ensamblado de E040](../results/e040_quick_holdout_linux/quick-assembly.txt).

El fallo anterior de `few` no tiene una explicación en la sustitución de redes observada aquí. Las copias registraron las mismas 15 particiones, 11 salidas `Sorted` sobre 123.543 claves y 56.470 claves en extremos que omiten recursión. `equal` salió del nodo raíz por `Sorted`. `alternating` hizo una partición, omitió un extremo de 90.006 claves y encontró un tramo constante de 90.007. El estado `Sorted` del pivote corresponde a un tramo constante. La entrada `sorted`, ordenada de antemano pero no constante, registró cero salidas por ese estado. Todas las entradas tuvieron cero `Only2Values` y cero fallback en el diagnóstico O3. [Contadores de E042-A](../results/e042_work_diagnostic/work.csv).

Las cuentas registran llamadas y longitudes. Quedan fuera los accesos internos del pivote y del particionador, las instrucciones dinámicas, los ciclos y el tráfico de memoria. La instrumentación modifica el código generado y puede alterar las llamadas de cola. Por eso la reproducibilidad de las cuentas y del hash respalda el mecanismo observado en las copias, con un límite al extrapolarlo al binario original.

## Qué varía con el ejecutable exacto de E040

E042-B ejecutó las mismas doce entradas en ocho procesos nuevos por entrada. Cada proceso realizó 31 rondas medidas más un calentamiento de los diez algoritmos. Se verificaron el ejecutable y las bibliotecas enlazadas antes y después. Quedaron 29.760 muestras medidas, 30.720 salidas exactas con `std::sort` y 96 mapas tempranos completos. La ordenación corrió en CPU lógica 2 y el observador en CPU lógica 0. Las entradas se eligieron para diagnosticar fallos y controles conocidos. [Resumen de E042-B](../results/e042_process_variation/summary.md), [integridad y entorno](../results/e042_process_variation/completion.json).

Un ratio mayor que 1 favorece a quick128. Cada rango nuevo reúne ocho ratios entre medianas del mismo proceso. La primera columna de ratios procede de la serie que registró la pérdida y se conserva aparte.

| Entrada | Ratio previo DSO256 / host, cada uno frente a quick128 | E042-B DSO256/quick128 | E042-B host/quick128 | Victorias por proceso DSO256 / host |
|---|---:|---:|---:|---:|
| 8193 skew 33013 (E040) | 0,898 / 0,883 | 1,104–1,126 | 1,090–1,129 | 8/8 / 8/8 |
| 180013 splitmix 14009 (E041) | 0,985 / 0,946 | 1,083–1,103 | 1,088–1,104 | 8/8 / 8/8 |
| 180013 few 58013 (E041) | 0,897 / 0,838 | 0,994–1,021 | 1,002–1,015 | 7/8 / 8/8 |
| 8209 forced_middle 58013 (E041) | 0,740 / 0,945 | 1,083–1,124 | 1,055–1,095 | 8/8 / 8/8 |
| 8209 forced_tail 41011 (E041) | 0,747 / 0,729 | 1,086–1,115 | 1,062–1,101 | 8/8 / 8/8 |
| 8209 forced_front 58013 (E041) | 0,783 / 0,767 | 1,065–1,104 | 1,054–1,074 | 8/8 / 8/8 |

El resultado `skew` coincide en signo con el recheck de E041 (1,121 frente a DSO256 y 1,109 frente al host). Las pérdidas fuertes de las seis entradas no reaparecen como medianas de proceso en E042-B. En `few` queda una pérdida leve frente a DSO256. E040 y E041 conservan sus resultados y sus criterios fallidos. [E040](../results/e040_quick_holdout_linux/analysis-quick.md), [E041](../results/e041_quick_holdout_exact/analysis-quick.md), [recheck E041](../results/e041_quick_problem_recheck/analysis-quick.md).

Los bloques prefijados de rondas 0–14 y 15–30 muestran oscilaciones que la mediana de proceso oculta.

- `forced_middle`, tanda 6, pasa de 1,087 a 0,955 frente a DSO256 y de 1,056 a 0,930 frente al host. `forced_front`, tanda 7, pasa de 1,071 a 0,985 frente al host. Ambas tandas favorecen a quick128 al usar las 31 rondas. En `forced_tail`, `skew` y `splitmix` 180013, los dos bloques de los ocho procesos favorecen a quick128 contra ambos controles.
- En `few`, el signo cambia entre bloques en cinco de ocho procesos frente a DSO256 y dos de ocho frente al host. Por ejemplo, en tanda 0, el ratio frente a DSO256 pasa de 1,010 a 0,988.
- En `equal`, quick128 gana cinco de ocho medianas frente a DSO256 y ocho de ocho frente al host. El signo entre bloques cambia en cinco y dos procesos, respectivamente. En `alternating` gana seis y cinco medianas, con cambios de signo en tres y cuatro procesos. Estas entradas registran rutas sin hojas en los dos umbrales.

[Medianas completas y bloques de cada proceso](../results/e042_process_variation/analysis-process.md).

Los cambios dentro del mismo proceso muestran que reiniciar el proceso no es un requisito para observarlos. Las cuentas de las copias y los tiempos del binario original se observaron en ejecuciones separadas. En conjunto debilitan una explicación que dependa solo de las diferencias en las cuentas, sin aislar la contribución de direcciones, caché, asignador o carga. Los mapas registran mappings tempranos, no direcciones por llamada. RSS, fallos de página y cambios de contexto abarcan generación, ordenación y comprobación. La frecuencia efectiva no se controló ni midió durante la ordenación. [Alcance de mapas y métricas de proceso](../results/e042_process_variation/summary.md).

## Incidencia de ASan/UBSan y recuperación

La ejecución original produjo seis salidas triviales correctas en `n=0`, `uniform`, semilla 12007. El segundo proceso, `n=0`, `uniform`, semilla 33013, entró en un bucle de `AddressSanitizer:DEADLYSIGNAL` sin traza útil. El wrapper evita llamar al sorter para esa longitud. Se conservó el estado y el log de 2.050.409.610 bytes, y se detuvo el proceso con SIGTERM. La matriz inicial quedó incompleta y la causa sigue abierta. [Estado del proceso](../results/e042_work_diagnostic/san-hang-process.txt), [seis salidas iniciales](../results/e042_work_diagnostic/sanitizers.csv).

Tras cerrar los tiempos, una recuperación registrada por separado usó las mismas bibliotecas instrumentadas y sanitizadas en un nuevo ejecutable no PIE con un único proceso persistente. Completó las 7464 salidas previstas con igualdad exacta, guardas y comprobación de cuentas. Salió con código 0 y stderr vacío. El cambio simultáneo de ejecutable y ciclo de vida impide atribuir el fallo original a uno de esos factores. La validación corresponde a esta configuración de recuperación. [Adenda](../results/e042_sanitizer_recovery/preregistration.md), [resultado](../results/e042_sanitizer_recovery/completion.json).

El coste de las redes sigue siendo una explicación parcial. También se observan cambios de ganador en entradas para las que las copias instrumentadas registran cero hojas. Quick128 permanece como candidato experimental y la escala se examina en una etapa aparte.
