# Conclusión E041

Candidato quick128 fijo; mismo binario y DSOs de E040, hashes verificados antes/después. El holdout falla el criterio estricto: gana17/18 random, pero pierde180013/SplitMix/14009 (control/candidato0.985329, host/candidato0.945620). Robustez falla180013/few/58013 (0.896836). Gana66/198 nominales ante mejor referencia; todos los negativos y la dispersión están en analysis-quick.md.

El recheck separado no reproduce la pérdida inicial8193/skew/33013, pero no borra E040 ni rescata E041. No se ajusta umbral ni selector. Próximo diagnóstico: separar trabajo de partición/hojas/fallback de variación entre procesos, antes de atribuir causa. No promover como sorter universal ni reclamar novedad.
