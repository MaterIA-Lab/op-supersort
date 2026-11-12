# E041-diagnostico — principal fijo quick128

Umbral128 frente a256 con DSOs aislados; referencia host SIMD informada siempre. Ratios>1 favorecen al principal. Casos nominales, no datasets independientes. No elegir ganador por entrada.

| n | distribución | semilla | principal ms | min–max ms | DSO256/principal | hostSIMD/principal | mejor referencia | referencia/principal |
|---:|---|---:|---:|---|---:|---:|---|---:|
| 8193 | dense16 | 12007 | 0.023484 | 0.019857–0.037640 | 1.110 | 1.107 | vq | 1.055 |
| 8193 | dense16 | 33013 | 0.022873 | 0.021760–0.032240 | 1.088 | 1.061 | vq | 1.047 |
| 8193 | skew | 12007 | 0.023434 | 0.019957–0.041026 | 1.119 | 1.111 | vq | 1.061 |
| 8193 | skew | 33013 | 0.023203 | 0.022401–0.032430 | 1.121 | 1.109 | vq | 1.049 |
| 8193 | uniform | 12007 | 0.024285 | 0.020819–0.037270 | 1.104 | 1.079 | vq | 1.038 |
| 8193 | uniform | 33013 | 0.025697 | 0.023083–0.055694 | 1.321 | 1.492 | vq | 1.239 |

| distribución | nominales | gana DSO256 | DSO256/principal | gana hostSIMD | host/principal | gana externas | referencia/principal |
|---|---:|---:|---|---:|---|---:|---|
| dense16 | 2 | 2 | 1.088–1.110 | 2 | 1.061–1.107 | 2 | 1.047–1.055 |
| skew | 2 | 2 | 1.119–1.121 | 2 | 1.109–1.111 | 2 | 1.049–1.061 |
| uniform | 2 | 2 | 1.104–1.321 | 2 | 1.079–1.492 | 2 | 1.038–1.239 |

Fallos uniform/SplitMix frente DSO: []

Pérdidas>10% robustez: []

Uniform/SplitMix sin victoria ante hostSIMD: []

Gana mejor referencia: 6/6 nominales.
