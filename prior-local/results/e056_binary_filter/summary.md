# E056 — Dos particiones binarias para la ventana

Medianas en ms. La puerta se aplica a la mezcla 50/50 en ambas semillas.

| Familia | Semilla | Binaria | E049 | Vqsort | E049 / binaria | Vqsort / binaria | Vqsort / E049 | Ruta binaria | Ruta E049 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| mixed | 42701 | 34.691717 | 39.886855 | 43.411834 | 1.149752 | 1.251360 | 1.088374 | window | window |
| mixed | 91009 | 32.070183 | 39.895951 | 40.439456 | 1.244020 | 1.260967 | 1.013623 | window | window |
| uniform | 42701 | 56.317875 | 56.270917 | 54.683654 | 0.999166 | 0.970982 | 0.971792 | vq | vq |
| uniform | 91009 | 50.441712 | 49.142038 | 49.815759 | 0.974234 | 0.987591 | 1.013710 | vq | vq |
| prefix_distinct | 42701 | 49.282864 | 48.662835 | 49.502543 | 0.987419 | 1.004458 | 1.017256 | vq | vq |
| prefix_distinct | 91009 | 50.520613 | 51.202447 | 50.655314 | 1.013496 | 1.002666 | 0.989314 | vq | vq |
| dense16 | 42701 | 19.122158 | 12.911442 | 39.586750 | 0.675208 | 2.070203 | 3.066021 | window | window |
| dense16 | 91009 | 17.280698 | 12.376203 | 37.962166 | 0.716187 | 2.196796 | 3.067352 | window | window |
| late_miss | 42701 | 39.941228 | 42.994729 | 36.713544 | 1.076450 | 0.919189 | 0.853908 | window | window |
| late_miss | 91009 | 41.070716 | 42.807711 | 37.669328 | 1.042293 | 0.917182 | 0.879966 | window | window |

Puerta del filtro superada.


210 muestras y 240 salidas exactas con calentamientos. 3243 comprobaciones previas.
