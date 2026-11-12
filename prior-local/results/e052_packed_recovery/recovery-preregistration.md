# E052 — Recuperación de la matriz por unidades de telemetría

2026-11-05. El primer binario compiló y produjo 408 comprobaciones exactas previas. Los cinco primeros procesos de rendimiento salieron con código 0. El analizador abortó en el quinto porque acotó `above128` y `above256` por el número de hojas. Los campos cuentan **claves en esas hojas**, así que su cota es n. El fallo no ocurrió dentro del sorter. Los dos residuales `external_mix` ya descartan el filtro por tiempo. Conservar los datos y la excepción originales.

Corregir solo la unidad del analizador. Con el mismo binario y dependencias verificadas por hash, reutilizar los cinco CSV por caso ya generados, comparar los primeros cuatro con `raw.csv` y ejecutar una sola vez los 21 restantes en orden original. Sin recompilar ni repetir casos completos. Abrir un directorio nuevo, conservar todos los logs y mantener las semillas, brazos, protocolo y umbrales del prerregistro.
