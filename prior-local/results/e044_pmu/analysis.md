# E044 — contadores por llamada

Medianas crudas, sin restar el control vacío. Eventos genéricos WSL. La copia común y std::sort de verificación están fuera de la región contada.

| n | distribución | semilla | algoritmo | ciclos | instrucciones | cache-misses | branch-misses | filas activas ≥99% |
|---:|---|---:|---|---:|---:|---:|---:|---:|
| 8193 | skew | 33013 | empty | 107 | 33 | 0 | 2 | 11/11 |
| 8193 | skew | 33013 | simd256dso | 96981 | 265397 | 65 | 16 | 11/11 |
| 8193 | skew | 33013 | quick128 | 78518 | 267886 | 49 | 11 | 11/11 |
| 8209 | forced_middle | 58013 | empty | 107 | 33 | 0 | 2 | 11/11 |
| 8209 | forced_middle | 58013 | simd256dso | 118819 | 277373 | 101 | 17 | 11/11 |
| 8209 | forced_middle | 58013 | quick128 | 100120 | 278500 | 84 | 35 | 11/11 |
| 180013 | splitmix | 14009 | empty | 97 | 33 | 0 | 2 | 11/11 |
| 180013 | splitmix | 14009 | simd256dso | 3130318 | 8088586 | 2992 | 13017 | 11/11 |
| 180013 | splitmix | 14009 | quick128 | 2808320 | 8092381 | 2605 | 17445 | 11/11 |
| 180013 | few | 58013 | empty | 95 | 33 | 0 | 2 | 11/11 |
| 180013 | few | 58013 | simd256dso | 642618 | 2147551 | 1764 | 2492 | 11/11 |
| 180013 | few | 58013 | quick128 | 635054 | 2147551 | 1752 | 2477 | 11/11 |
| 180013 | equal | 14009 | empty | 103 | 33 | 0 | 2 | 11/11 |
| 180013 | equal | 14009 | simd256dso | 135596 | 180392 | 332 | 11 | 11/11 |
| 180013 | equal | 14009 | quick128 | 135908 | 180392 | 326 | 13 | 11/11 |
| 10000000 | uniform | 60101 | empty | 97 | 33 | 0 | 2 | 11/11 |
| 10000000 | uniform | 60101 | simd256dso | 241771895 | 606553021 | 337129 | 1102583 | 11/11 |
| 10000000 | uniform | 60101 | quick128 | 225699371 | 607391572 | 299644 | 1407302 | 11/11 |
| 10000000 | few | 73529 | empty | 99 | 33 | 0 | 2 | 11/11 |
| 10000000 | few | 73529 | simd256dso | 54911145 | 117197030 | 107456 | 168161 | 11/11 |
| 10000000 | few | 73529 | quick128 | 47763633 | 117197027 | 98137 | 168200 | 11/11 |
| 10000000 | forced_middle | 60101 | empty | 105 | 33 | 0 | 2 | 11/11 |
| 10000000 | forced_middle | 60101 | simd256dso | 259211707 | 649701987 | 358034 | 1140667 | 11/11 |
| 10000000 | forced_middle | 60101 | quick128 | 251508824 | 654505790 | 301688 | 1478412 | 11/11 |

176 llamadas medidas y 192 salidas exactas con calentamientos. 88 controles vacíos. Las filas con multiplexación se conservan en raw.csv. Los misses no se convierten en bytes DRAM ni establecen causalidad.
