# E054 — Comparación completa del compuesto

Las razones dividen la mediana de la referencia por la del compuesto. La mejor externa se elige entre vqsort, x86-simd-sort e IPS2Ra.

## Matriz principal

| Familia | Semilla | Compuesto, ms | E047, ms | Striped, ms | Vqsort, ms | SIMD, ms | IPS2Ra, ms | Mejor externa | Mejor / compuesto | E047 / compuesto | Striped / compuesto | Ruta (examinadas, propuestas) | Meta |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| uniform | 42701 | 48.414296 | 47.948394 | 48.179313 | 47.712803 | 53.724328 | 153.901769 | vq | 0.985511 | 0.990377 | 0.995146 | dict_bypass (0, 17) | Falla |
| uniform | 91009 | 48.659603 | 49.299937 | 48.299309 | 48.846831 | 53.631056 | 156.685376 | vq | 1.003848 | 1.013159 | 0.992596 | dict_bypass (0, 17) | Falla |
| prefix_distinct | 42701 | 48.614277 | 49.446961 | 47.883525 | 48.783291 | 53.109357 | 147.018157 | vq | 1.003477 | 1.017128 | 0.984968 | dict_bypass (0, 17) | Falla |
| prefix_distinct | 91009 | 47.564680 | 47.715110 | 47.752630 | 48.455161 | 53.102133 | 154.606670 | vq | 1.018721 | 1.003163 | 1.003951 | dict_bypass (0, 17) | Falla |
| dense16 | 42701 | 12.947532 | 13.639573 | 35.058134 | 35.133916 | 50.873582 | 36.994011 | vq | 2.713561 | 1.053450 | 2.707708 | window_one (10000000, 1) | Pasa |
| dense16 | 91009 | 12.767325 | 12.878172 | 35.073826 | 34.714876 | 49.762159 | 35.961984 | vq | 2.719041 | 1.008682 | 2.747155 | window_one (10000000, 1) | Pasa |
| skew | 42701 | 14.364937 | 13.924214 | 25.067406 | 24.813434 | 27.639598 | 61.093460 | vq | 1.727361 | 0.969320 | 1.745041 | window_one (10000000, 1) | Pasa |
| skew | 91009 | 14.841587 | 14.282614 | 26.243242 | 26.096397 | 29.411678 | 61.606829 | vq | 1.758329 | 0.962337 | 1.768223 | window_one (10000000, 1) | Pasa |
| mixed | 42701 | 37.244686 | 38.245734 | 37.926047 | 38.688962 | 41.081476 | 122.907285 | vq | 1.038778 | 1.026878 | 1.018294 | dict_bypass (0, 17) | Falla |
| mixed | 91009 | 38.347074 | 37.417259 | 38.312970 | 38.040473 | 42.112653 | 122.820191 | vq | 0.992005 | 0.975753 | 0.999111 | dict_bypass (0, 17) | Falla |
| bimodal | 42701 | 12.277590 | 12.404487 | 26.384244 | 27.291527 | 29.236456 | 60.539296 | vq | 2.222873 | 1.010336 | 2.148976 | window_two (10000000, 2) | Pasa |
| bimodal | 91009 | 13.463504 | 13.493381 | 26.503828 | 26.939342 | 29.921687 | 61.004443 | vq | 2.000916 | 1.002219 | 1.968568 | window_two (10000000, 2) | Pasa |
| few | 42701 | 7.353568 | 12.158408 | 7.144108 | 11.732753 | 12.198621 | 36.496553 | vq | 1.595518 | 1.653403 | 0.971516 | dict_counted (10000000, 16) | Pasa |
| few | 91009 | 7.911188 | 12.407393 | 7.723289 | 12.504845 | 13.670061 | 37.695822 | vq | 1.580653 | 1.568335 | 0.976249 | dict_counted (10000000, 16) | Pasa |
| few_permute | 42701 | 7.701848 | 11.825316 | 7.727395 | 11.579237 | 12.419485 | 39.633449 | vq | 1.503436 | 1.535387 | 1.003317 | dict_counted (10000000, 16) | Pasa |
| few_permute | 91009 | 7.448474 | 11.193507 | 7.406635 | 11.097835 | 11.391403 | 38.597395 | vq | 1.489947 | 1.502792 | 0.994383 | dict_counted (10000000, 16) | Pasa |
| few_dominant | 42701 | 13.156266 | 12.331919 | 8.471342 | 8.580868 | 20.550779 | 37.071978 | vq | 0.652227 | 0.937342 | 0.643902 | window_one (10000000, 1) | Falla |
| few_dominant | 91009 | 13.285038 | 12.805823 | 8.191880 | 9.862620 | 9.124761 | 37.030480 | simd | 0.686845 | 0.963928 | 0.616625 | window_one (10000000, 1) | Falla |
| few_powers | 42701 | 9.556638 | 8.889713 | 11.173055 | 11.354294 | 11.945698 | 44.258491 | vq | 1.188105 | 0.930213 | 1.169141 | window_one (10000000, 1) | Falla |
| few_powers | 91009 | 9.903126 | 9.155240 | 10.977391 | 11.251933 | 12.927881 | 44.165589 | vq | 1.136200 | 0.924480 | 1.108477 | window_one (10000000, 1) | Falla |
| equal | 42701 | 1.709921 | 1.863325 | 1.589006 | 1.829684 | 1.779602 | 5.193955 | simd | 1.040751 | 1.089714 | 0.929286 | window_constant (10000000, 1) | Falla |
| equal | 91009 | 1.736256 | 1.713528 | 2.128994 | 1.824386 | 1.994704 | 5.546684 | vq | 1.050759 | 0.986910 | 1.226198 | window_constant (10000000, 1) | Falla |

## Adversarios de rechazo

| Familia | Semilla | Compuesto, ms | E047, ms | Striped, ms | Vqsort, ms | SIMD, ms | IPS2Ra, ms | Mejor externa | Mejor / compuesto | E047 / compuesto | Striped / compuesto | Ruta (examinadas, propuestas) | Meta |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| early_unknown | 42701 | 11.871651 | 11.279716 | 11.323279 | 11.258335 | 11.406394 | 36.406834 | vq | 0.948338 | 0.950139 | 0.953808 | dict_reject (4, 16) | Control |
| early_unknown | 91009 | 11.513533 | 10.911669 | 11.204246 | 11.330844 | 11.986986 | 35.417442 | vq | 0.984133 | 0.947726 | 0.973137 | dict_reject (4, 16) | Control |
| late_unknown | 42701 | 14.625513 | 11.164902 | 14.910646 | 11.570119 | 11.657201 | 36.625851 | vq | 0.791091 | 0.763385 | 1.019496 | dict_reject (10000000, 16) | Control |
| late_unknown | 91009 | 14.950551 | 11.088650 | 15.646017 | 11.327315 | 11.847958 | 35.467881 | vq | 0.757652 | 0.741688 | 1.046518 | dict_reject (10000000, 16) | Control |
| late_reject | 42701 | 40.147808 | 39.396354 | 38.042738 | 37.989318 | 51.784680 | 51.537217 | vq | 0.946236 | 0.981283 | 0.947567 | window_reject (10000000, 1) | Control |
| late_reject | 91009 | 39.779658 | 38.913820 | 38.618040 | 37.981422 | 51.588029 | 51.931211 | vq | 0.954795 | 0.978234 | 0.970799 | window_reject (10000000, 1) | Control |

## Control casi ordenado

| Familia | Semilla | Compuesto, ms | E047, ms | Striped, ms | Vqsort, ms | SIMD, ms | IPS2Ra, ms | Mejor externa | Mejor / compuesto | E047 / compuesto | Striped / compuesto | Ruta (examinadas, propuestas) | Meta |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| near_sorted | 42701 | 51.490337 | 51.787512 | 50.473208 | 50.679064 | 48.572242 | 122.266085 | simd | 0.943327 | 1.005771 | 0.980246 | dict_bypass (0, 17) | Control |
| near_sorted | 91009 | 51.355545 | 50.444117 | 50.806011 | 51.667500 | 49.185075 | 121.566911 | simd | 0.957736 | 0.982253 | 0.989299 | dict_bypass (0, 17) | Control |

Meta de 1,25× en 10/22 casos principales.
Cobertura del diccionario superada.
Menor mediana que la mejor externa en 18/30 casos totales.

## Incumplimientos de la meta general

- uniform/42701 obtuvo 0.985511 frente a vq, por debajo de 1,25.
- uniform/91009 obtuvo 1.003848 frente a vq, por debajo de 1,25.
- prefix_distinct/42701 obtuvo 1.003477 frente a vq, por debajo de 1,25.
- prefix_distinct/91009 obtuvo 1.018721 frente a vq, por debajo de 1,25.
- mixed/42701 obtuvo 1.038778 frente a vq, por debajo de 1,25.
- mixed/91009 obtuvo 0.992005 frente a vq, por debajo de 1,25.
- few_dominant/42701 obtuvo 0.652227 frente a vq, por debajo de 1,25.
- few_dominant/91009 obtuvo 0.686845 frente a simd, por debajo de 1,25.
- few_powers/42701 obtuvo 1.188105 frente a vq, por debajo de 1,25.
- few_powers/91009 obtuvo 1.136200 frente a vq, por debajo de 1,25.
- equal/42701 obtuvo 1.040751 frente a simd, por debajo de 1,25.
- equal/91009 obtuvo 1.050759 frente a vq, por debajo de 1,25.

## Pérdidas del compuesto

- uniform/42701 perdió frente a e047 (0.990377), striped (0.995146), vq (0.985511).
- uniform/91009 perdió frente a striped (0.992596).
- prefix_distinct/42701 perdió frente a striped (0.984968).
- skew/42701 perdió frente a e047 (0.969320).
- skew/91009 perdió frente a e047 (0.962337).
- mixed/91009 perdió frente a e047 (0.975753), striped (0.999111), vq (0.992005).
- few/42701 perdió frente a striped (0.971516).
- few/91009 perdió frente a striped (0.976249).
- few_permute/91009 perdió frente a striped (0.994383).
- few_dominant/42701 perdió frente a e047 (0.937342), striped (0.643902), vq (0.652227).
- few_dominant/91009 perdió frente a e047 (0.963928), striped (0.616625), vq (0.742386), simd (0.686845).
- few_powers/42701 perdió frente a e047 (0.930213).
- few_powers/91009 perdió frente a e047 (0.924480).
- equal/42701 perdió frente a striped (0.929286).
- equal/91009 perdió frente a e047 (0.986910).
- early_unknown/42701 perdió frente a e047 (0.950139), striped (0.953808), vq (0.948338), simd (0.960809).
- early_unknown/91009 perdió frente a e047 (0.947726), striped (0.973137), vq (0.984133).
- late_unknown/42701 perdió frente a e047 (0.763385), vq (0.791091), simd (0.797046).
- late_unknown/91009 perdió frente a e047 (0.741688), vq (0.757652), simd (0.792476).
- late_reject/42701 perdió frente a e047 (0.981283), striped (0.947567), vq (0.946236).
- late_reject/91009 perdió frente a e047 (0.978234), striped (0.970799), vq (0.954795).
- near_sorted/42701 perdió frente a striped (0.980246), vq (0.984244), simd (0.943327).
- near_sorted/91009 perdió frente a e047 (0.982253), striped (0.989299), simd (0.957736).

1260 muestras y 1440 salidas exactas con calentamientos. 786 comprobaciones previas de correctitud.
