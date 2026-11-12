# Árbol de mezclas y movimientos

2026-11-05. Propuesta razonada posterior a implementar E037; **E038 aún no ejecutada ni preregistrada**. No es una nueva victoria ni una reclamación de novedad. Conecta [[07 - Hipótesis CPU quicksort mergesort]] y [[E037 - Prerregistro runs naturales]].

## Dos cantidades que no conviene confundir

El árbol define C_tree = sum(longitud de cada fusión prevista). Cada elemento aparece tantas veces como profundidad tiene su run en el árbol. Si los runs tienen longitudes desiguales, equilibrar su número no minimiza ese volumen: puede colocar un run enorme muy profundo.

Pero el test max(izquierda)<=min(derecha) puede omitir trabajo. Por eso C_exec = sum(longitud de fusiones realmente ejecutadas) puede diferir de C_tree, y reducir el primero no garantiza la misma reducción del segundo. Además E037 escribe n elementos por nivel aunque parte se copie: su coste no depende solo de C_exec. En una entrada de73001 de run_heavy, el diagnóstico preliminar muestra más elementos mezclados reales en natural que fixed aunque tenga menos niveles; se conserva el dato como motivo del siguiente contraste, no para cambiar E037.

## Cómo aislar política sin confundirla con buffers

Para E038 convendría formar los mismos runs natural128 y producir un plan de ternas(lo,mid,hi) en orden válido de ejecución. Control: parejas. Principal: política Powersort por longitudes, con algoritmo fijado previamente. Mismo ejecutor para ambos: si fronteras ordenadas, no hacer nada; si no, std::merge hacia scratch[lo:hi] y copia de vuelta a data[lo:hi]. Misma reserva de scratch, descriptores y plan, dentro del tiempo. No sustituir ese test/copia por kernels diferentes entre políticas.

Así cada run reside en data y el árbol puede ser desigual sin gestionar propietarios de buffers. Es otro contraste y otra coreografía: NO comparar su tiempo directamente con E037 y atribuir toda diferencia al árbol. Incluir el candidato E037 en el mismo binario como control práctico adicional.

El árbol debe ser alfabético: solo mezcla intervalos adyacentes. Huffman libre no sirve para este kernel contiguo. Powersort es antecedente y referencia, no una idea nueva nuestra.

## Predicciones y advertencias antes de registrar

Un run dominante al principio/centro/final, longitudes geométricas, runs equilibrados y random distinguen beneficios de sobrecoste. No asumir que el control por parejas siempre entierra un run enorme: una cola impar puede llegar a la raíz con pocas fusiones, dependiendo del número de runs. Analizar profundidades del plan ANTES de medir para no exigir una mejora matemáticamente imposible ni seleccionar casos favorables después.

Fijar primero conjunto de longitudes y posiciones, incluido un caso en el que el control ya sea bueno. Medir los runs reales: sortear bloques uniformes no garantiza fronteras exactas. Si se necesita controlar el árbol, construir fronteras forzadas sin cambiar el multiconjunto entre algoritmos y describir ese nuevo generador.

Para cada fusión ejecutada de m claves, merge-to-scratch+copyback tiene aproximadamente16m bytes de tráfico lógico (leer entrada, escribir scratch, leer scratch, escribir entrada), excluyendo detección, hojas y metadatos. Eso NO es tráfico DRAM medido. Menos movimiento puede no bajar el tiempo por planificación, ramas o localidad; los contadores hardware siguen pendientes.

## Relación con quicksort

La misma idea de balancear trabajo por coste exige cuidado en quicksort: pivotes equilibrados reducen profundidad, pero un particionador SIMD, duplicados y hojas discretas cambian el coste local. No trasplantar el árbol de runs a quicksort ni afirmar mejora de quicksort por un resultado de mergesort. El diagnóstico E035 invita a medir redes y presión de registros dentro del quicksort original, con garantías de profundidad y tratamiento de iguales intactas.
