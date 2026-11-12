# E052 — Filtro de hojas de 16 bits

Cada cociente divide la mediana de la referencia por la de packed. Los ahorros en ms son la mediana de la referencia menos la de packed.

| n | Familia | Semilla | Wide, ms | Packed, ms | Vqsort, ms | Wide / packed | Vqsort / packed | Wide − packed, ms | Vqsort − packed, ms | Grupos | Hojas | Claves en hojas >128 | Claves en hojas >256 | Puerta |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5000000 | uniform | 39607 | 34.460867 | 36.016992 | 22.719159 | 0.956795 | 0.630790 | -1.556125 | -13.297833 | 256 | 65536 | 0 | 0 | Diagnóstico |
| 5000000 | uniform | 82723 | 36.797159 | 36.836670 | 22.920836 | 0.998927 | 0.622229 | -0.039511 | -13.915834 | 256 | 65536 | 0 | 0 | Diagnóstico |
| 5000000 | external_mix | 39607 | 35.755743 | 35.923477 | 23.580989 | 0.995331 | 0.656423 | -0.167734 | -12.342488 | 256 | 65535 | 0 | 0 | Falla |
| 5000000 | external_mix | 82723 | 35.423003 | 36.128330 | 23.244762 | 0.980477 | 0.643394 | -0.705327 | -12.883568 | 256 | 65535 | 0 | 0 | Falla |
| 5000000 | external_low | 39607 | 34.348537 | 35.244841 | 22.695335 | 0.974569 | 0.643934 | -0.896304 | -12.549506 | 128 | 32768 | 4907498 | 0 | Falla |
| 5000000 | external_low | 82723 | 38.436579 | 34.632406 | 26.236618 | 1.109844 | 0.757574 | +3.804173 | -8.395788 | 128 | 32768 | 4901277 | 0 | Falla |
| 5000000 | prefix_distinct | 39607 | 36.400246 | 48.486904 | 23.095233 | 0.750723 | 0.476319 | -12.086658 | -25.391671 | 4 | 1024 | 5000000 | 5000000 | Falla |
| 5000000 | prefix_distinct | 82723 | 35.327503 | 45.475921 | 21.996922 | 0.776840 | 0.483705 | -10.148418 | -23.478999 | 4 | 1024 | 5000000 | 5000000 | Falla |
| 5000000 | bimodal | 39607 | 32.160960 | 60.205806 | 12.552949 | 0.534184 | 0.208501 | -28.044846 | -47.652857 | 2 | 2 | 5000000 | 5000000 | Diagnóstico |
| 5000000 | bimodal | 82723 | 33.493609 | 60.069602 | 12.363405 | 0.557580 | 0.205818 | -26.575993 | -47.706197 | 2 | 2 | 5000000 | 5000000 | Diagnóstico |
| 10000000 | uniform | 39607 | 78.889180 | 80.118506 | 46.927253 | 0.984656 | 0.585723 | -1.229326 | -33.191253 | 256 | 65536 | 9814462 | 0 | Falla |
| 10000000 | uniform | 82723 | 83.005557 | 81.014679 | 48.407104 | 1.024574 | 0.597510 | +1.990878 | -32.607575 | 256 | 65536 | 9803839 | 0 | Falla |
| 10000000 | prefix_distinct | 39607 | 89.826232 | 116.576611 | 46.881077 | 0.770534 | 0.402148 | -26.750379 | -69.695534 | 4 | 1024 | 10000000 | 10000000 | Falla |
| 10000000 | prefix_distinct | 82723 | 90.263199 | 117.105769 | 48.015293 | 0.770784 | 0.410016 | -26.842570 | -69.090476 | 4 | 1024 | 10000000 | 10000000 | Falla |
| 10000000 | dense16 | 39607 | 68.008254 | 133.594575 | 36.231391 | 0.509064 | 0.271204 | -65.586321 | -97.363184 | 1 | 1 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | dense16 | 82723 | 66.737566 | 131.740390 | 38.768916 | 0.506584 | 0.294283 | -65.002824 | -92.971474 | 1 | 1 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | skew | 39607 | 99.233737 | 137.691582 | 25.922362 | 0.720696 | 0.188264 | -38.457845 | -111.769220 | 256 | 65495 | 9499182 | 9499182 | Diagnóstico |
| 10000000 | skew | 82723 | 98.206185 | 135.609873 | 25.884310 | 0.724182 | 0.190873 | -37.403688 | -109.725563 | 256 | 65497 | 9498795 | 9498795 | Diagnóstico |
| 10000000 | mixed | 39607 | 85.522246 | 115.413666 | 38.002355 | 0.741006 | 0.329271 | -29.891420 | -77.411311 | 256 | 65536 | 5002500 | 5002500 | Diagnóstico |
| 10000000 | mixed | 82723 | 85.401012 | 113.605838 | 37.748110 | 0.751731 | 0.332273 | -28.204826 | -75.857728 | 256 | 65536 | 4999399 | 4999399 | Diagnóstico |
| 10000000 | bimodal | 39607 | 88.668526 | 141.786880 | 28.203304 | 0.625365 | 0.198913 | -53.118354 | -113.583576 | 2 | 2 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | bimodal | 82723 | 85.257072 | 137.902018 | 27.810153 | 0.618244 | 0.201666 | -52.644946 | -110.091865 | 2 | 2 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | few | 39607 | 59.460054 | 61.123969 | 12.540458 | 0.972778 | 0.205164 | -1.663915 | -48.583511 | 16 | 16 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | few | 82723 | 58.846867 | 59.902779 | 12.400197 | 0.982373 | 0.207005 | -1.055912 | -47.502582 | 16 | 16 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | equal | 39607 | 33.273801 | 20.507521 | 1.879618 | 1.622517 | 0.091655 | +12.766280 | -18.627903 | 1 | 1 | 10000000 | 10000000 | Diagnóstico |
| 10000000 | equal | 82723 | 32.691360 | 19.634529 | 1.954359 | 1.664993 | 0.099537 | +13.056831 | -17.680170 | 1 | 1 | 10000000 | 10000000 | Diagnóstico |

**Filtro fallido.**

- 5000000/external_mix/39607 obtuvo -12.342488 en ahorro ante vqsort, ms, por debajo de 4.00.
- 5000000/external_mix/39607 obtuvo 0.995331 en wide/packed, por debajo de 1.10.
- 5000000/external_mix/82723 obtuvo -12.883568 en ahorro ante vqsort, ms, por debajo de 4.00.
- 5000000/external_mix/82723 obtuvo 0.980477 en wide/packed, por debajo de 1.10.
- 5000000/external_low/39607 obtuvo 0.643934 en vqsort/packed, por debajo de 0.90.
- 5000000/external_low/82723 obtuvo 0.757574 en vqsort/packed, por debajo de 0.90.
- 5000000/prefix_distinct/39607 obtuvo 0.476319 en vqsort/packed, por debajo de 0.90.
- 5000000/prefix_distinct/82723 obtuvo 0.483705 en vqsort/packed, por debajo de 0.90.
- 10000000/uniform/39607 obtuvo 0.585723 en vqsort/packed, por debajo de 1.25.
- 10000000/uniform/39607 obtuvo 0.984656 en wide/packed, por debajo de 1.10.
- 10000000/uniform/82723 obtuvo 0.597510 en vqsort/packed, por debajo de 1.25.
- 10000000/uniform/82723 obtuvo 1.024574 en wide/packed, por debajo de 1.10.
- 10000000/prefix_distinct/39607 obtuvo 0.402148 en vqsort/packed, por debajo de 0.90.
- 10000000/prefix_distinct/82723 obtuvo 0.410016 en vqsort/packed, por debajo de 0.90.

## Pérdidas de packed

- 5000000/uniform/39607 perdió frente a wide (0.956795), vq (0.630790).
- 5000000/uniform/82723 perdió frente a wide (0.998927), vq (0.622229).
- 5000000/external_mix/39607 perdió frente a wide (0.995331), vq (0.656423).
- 5000000/external_mix/82723 perdió frente a wide (0.980477), vq (0.643394).
- 5000000/external_low/39607 perdió frente a wide (0.974569), vq (0.643934).
- 5000000/external_low/82723 perdió frente a vq (0.757574).
- 5000000/prefix_distinct/39607 perdió frente a wide (0.750723), vq (0.476319).
- 5000000/prefix_distinct/82723 perdió frente a wide (0.776840), vq (0.483705).
- 5000000/bimodal/39607 perdió frente a wide (0.534184), vq (0.208501).
- 5000000/bimodal/82723 perdió frente a wide (0.557580), vq (0.205818).
- 10000000/uniform/39607 perdió frente a wide (0.984656), vq (0.585723).
- 10000000/uniform/82723 perdió frente a vq (0.597510).
- 10000000/prefix_distinct/39607 perdió frente a wide (0.770534), vq (0.402148).
- 10000000/prefix_distinct/82723 perdió frente a wide (0.770784), vq (0.410016).
- 10000000/dense16/39607 perdió frente a wide (0.509064), vq (0.271204).
- 10000000/dense16/82723 perdió frente a wide (0.506584), vq (0.294283).
- 10000000/skew/39607 perdió frente a wide (0.720696), vq (0.188264).
- 10000000/skew/82723 perdió frente a wide (0.724182), vq (0.190873).
- 10000000/mixed/39607 perdió frente a wide (0.741006), vq (0.329271).
- 10000000/mixed/82723 perdió frente a wide (0.751731), vq (0.332273).
- 10000000/bimodal/39607 perdió frente a wide (0.625365), vq (0.198913).
- 10000000/bimodal/82723 perdió frente a wide (0.618244), vq (0.201666).
- 10000000/few/39607 perdió frente a wide (0.972778), vq (0.205164).
- 10000000/few/82723 perdió frente a wide (0.982373), vq (0.207005).
- 10000000/equal/39607 perdió frente a vq (0.091655).
- 10000000/equal/82723 perdió frente a vq (0.099537).

546 muestras y 624 salidas exactas con calentamientos. 408 comprobaciones previas de correctitud.
