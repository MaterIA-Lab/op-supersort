# E042-B — variación entre procesos

Diagnóstico prefijado, sin promoción de candidato. Ejecutable y DSOs E040 verificados antes/después; salidas exactas contra std::sort en cada llamada. Ocho procesos por entrada, 31 rondas medidas y un calentamiento por algoritmo. Reutilización deliberada de fallos y controles: no es un holdout independiente.

Ratio >1 favorece quick128. Rangos entre las ocho medianas por proceso. No se mezclan rondas como datasets independientes. La captura de mapas puede perturbar; direcciones y rusage no identifican una causa de las diferencias.

| n | distribución | semilla | quick128 mediana ms, rango | DSO256/quick128, rango | victorias /8 | host/quick128, rango | victorias /8 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 8193 | skew | 33013 | 0.022432–0.023323 | 1.104018–1.126135 | 8 | 1.089997–1.129162 | 8 |
| 8193 | uniform | 33013 | 0.022532–0.023474 | 1.115454–1.143819 | 8 | 1.110930–1.128483 | 8 |
| 180013 | splitmix | 14009 | 0.622129–0.658506 | 1.082952–1.103033 | 8 | 1.088467–1.103761 | 8 |
| 180013 | few | 58013 | 0.144900–0.152474 | 0.993688–1.021049 | 7 | 1.001720–1.015268 | 8 |
| 8209 | forced_middle | 58013 | 0.023123–0.025017 | 1.082888–1.124335 | 8 | 1.054849–1.095316 | 8 |
| 8209 | forced_tail | 41011 | 0.023945–0.025768 | 1.085759–1.114830 | 8 | 1.062229–1.100851 | 8 |
| 8209 | forced_front | 58013 | 0.023374–0.024615 | 1.064757–1.104133 | 8 | 1.054154–1.073798 | 8 |
| 180013 | uniform | 41011 | 0.618452–0.651253 | 1.086920–1.102520 | 8 | 1.080811–1.103781 | 8 |
| 1500007 | splitmix | 58013 | 5.954700–6.272770 | 1.085726–1.106472 | 8 | 1.078214–1.100939 | 8 |
| 180013 | equal | 14009 | 0.029074–0.035636 | 0.967673–1.026677 | 5 | 1.022294–1.047533 | 8 |
| 180013 | sorted | 14009 | 0.574149–0.621017 | 1.061888–1.075623 | 8 | 1.038411–1.061836 | 8 |
| 180013 | alternating | 14009 | 0.035416–0.038853 | 0.980585–1.024869 | 6 | 0.983904–1.008748 | 5 |

29760 muestras medidas; 30720 salidas exactas incluyendo calentamientos. Mapas completos tempranos: 96/96.

RSS máximo, page faults y cambios de contexto corresponden al proceso completo, incluida generación y verificación; no son contadores de la región de ordenación. Frecuencia/carga no controladas. No se atribuye causalidad a ASLR, caché, asignador o frecuencia.

[Todas las medianas por proceso y ambos bloques](analysis-process.md).
