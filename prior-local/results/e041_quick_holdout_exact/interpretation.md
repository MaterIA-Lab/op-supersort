# E041 — conclusión cerrada

Quick128fijo, sin compilación ni ajuste respecto aE040. SHA256binario/DSOsverificados antes/después. Falla criterioestricto:17/18random, pierde180013/SplitMix/14009 (control/principal0.985329,host/principal0.945620). Robustezfalla180013/few/58013 (0.896836).66/198nominales frente mejorreferencia; negativoscompletos enanalysis-quick.md. No proponer selector retrospectivo ni promoción universal.

Diagnóstico preregistrado aparte no reproduce el anterior8193/skew/33013 (ahora1.121frenteDSO), pero no borra E040 ni rescata esteholdout. No atribuir causa a allocator/caché/ASLR/frecuencia sin aislarla. Próximo paso razonado: perfiles de trabajo y variación entre procesos, no barrido de parámetros.
