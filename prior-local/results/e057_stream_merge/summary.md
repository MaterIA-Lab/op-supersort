# E057 — Unión encadenada con bloques en caché

Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.

| Familia | Semilla | Bulk | Stream | Vqsort | Bulk / stream | Vqsort / stream | Vqsort / bulk | Ruta bulk | Ruta stream |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| uniform | 42701 | 106.174984 | 88.934658 | 45.977423 | 1.193854 | 0.516980 | 0.433034 | merge | merge |
| uniform | 91009 | 106.892000 | 91.364794 | 48.064054 | 1.169947 | 0.526068 | 0.449651 | merge | merge |
| prefix_distinct | 42701 | 100.079031 | 82.720677 | 45.596056 | 1.209843 | 0.551205 | 0.455600 | merge | merge |
| prefix_distinct | 91009 | 100.391212 | 83.526102 | 46.032541 | 1.201914 | 0.551116 | 0.458532 | merge | merge |
| mixed | 42701 | 105.708773 | 88.826699 | 35.970223 | 1.190056 | 0.404948 | 0.340277 | merge | merge |
| mixed | 91009 | 104.097371 | 87.254092 | 35.445724 | 1.193037 | 0.406236 | 0.340505 | merge | merge |
| dense16 | 42701 | 104.173240 | 87.133012 | 33.029394 | 1.195566 | 0.379069 | 0.317062 | merge | merge |
| dense16 | 91009 | 103.832525 | 87.362573 | 33.554401 | 1.188524 | 0.384082 | 0.323159 | merge | merge |

Puerta del filtro fallida.

- uniform/42701 alcanzó 0.516980 frente a vqsort, por debajo de 1.25.
- uniform/91009 alcanzó 0.526068 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.551205 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.551116 frente a vqsort, por debajo de 1.25.

168 muestras y 192 salidas exactas con calentamientos. 1320 comprobaciones previas.
