# E059 — Alternar bloques de particiones hermanas

Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.

| Familia | Semilla | Serial | Alternado | Vqsort | Serial − alternado (ms) | Serial / alternado | Vqsort / alternado |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform | 42701 | 50.118023 | 47.321476 | 46.812427 | 2.796547 | 1.059097 | 0.989243 |
| uniform | 91009 | 49.809066 | 46.606532 | 46.772742 | 3.202534 | 1.068714 | 1.003566 |
| prefix_distinct | 42701 | 50.306426 | 47.864179 | 46.469357 | 2.442247 | 1.051025 | 0.970859 |
| prefix_distinct | 91009 | 49.657395 | 46.902907 | 46.386202 | 2.754488 | 1.058727 | 0.988984 |
| equal | 42701 | 1.666820 | 1.873956 | 1.669715 | -0.207136 | 0.889466 | 0.891011 |
| equal | 91009 | 1.531247 | 1.608231 | 1.651029 | -0.076984 | 0.952131 | 1.026612 |

Puerta del filtro fallida.

- uniform/42701 alcanzó 0.989243 frente a vqsort, por debajo de 1.25.
- uniform/91009 alcanzó 1.003566 frente a vqsort, por debajo de 1.25.
- prefix_distinct/42701 alcanzó 0.970859 frente a vqsort, por debajo de 1.25.
- prefix_distinct/91009 alcanzó 0.988984 frente a vqsort, por debajo de 1.25.

126 muestras y 144 salidas exactas con calentamientos. 1590 comprobaciones previas.
