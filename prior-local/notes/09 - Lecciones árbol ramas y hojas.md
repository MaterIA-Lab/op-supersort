# Lecciones: árbol, ramas y hojas

2026-11-05. Síntesis de E038/E039 y motivación de E040, sin reclamar novedad ni elegir ganadores retrospectivamente.

## E038: reducir trabajo con un modelo comprobable

El árbol ponderado redujo exactamente los volúmenes previstos de las entradas forzadas y ganó las16 front/middle por1.279–1.554x frente al mismo ejecutor con parejas. Tail tuvo volumen idéntico y no era un caso donde exigir mejora. Esta separación entre predicción estructural y tiempo evita explicar cualquier resultado después de observarlo.

La reducción de C_tree de~3x/~2.48x no produjo aceleración del mismo factor. Parte del trabajo evitado puede ser más barato por patrones de selección previsibles, y planificación/lectura inicial siguen ahí. No se han medido ciclos, fallos de rama ni DRAM: esas son hipótesis para perfilar, no atribuciones demostradas. El resultado solo es competitivo frente a ese control; no ante toda la referencia SIMD.

## E039: quitar una rama no quita el coste de dependencia

El ensamblado sí usó cmov/setcc para seleccionar claves. La mejora uniforme fue solo0.9–2.8%, mientras few llegó a ser3.89x más lento. La fuente C++ sin if no basta para declarar éxito: primero se verifica la traducción y luego el resultado completo.

Razones posibles, no aisladas causalmente: la rama de std::merge puede ser muy predecible en largas secuencias de iguales; el kernel manual vuelve a cargar cabeceras y depende de índices actualizados; cmov no ofrece paralelismo vectorial. Igualdad de C_exec no implica igualdad del coste por elemento. Equal tuvo diferencias aun sin ejecutar ninguna mezcla: ni siquiera todas las pérdidas son atribuibles al kernel, y hay que conservar el límite de código generado/layout/entorno.

No añadir inmediatamente un selector de distribución para salvar una ganancia random tan pequeña. El selector cuesta observación y también puede equivocarse. Si se investiga adaptatividad, se necesita un mecanismo barato y un margen suficiente medido fuera del ajuste, no una tabla retrospectiva de ganadores.

## E040: atacar la hoja de quicksort con un cambio único

E035 mostró coste escalonado de redes. La hipótesis concreta de E040 es una partición más frente a una red menor, sin cambiar pivote, particionador, iguales ni protección de peor caso. Se contrastará en sorter completo y frente al host original, no solo contra un microkernel o un wrapper de coste diferente. Dos DSOs aislados evitan que las dos definiciones de templates terminen resolviendo a una misma implementación.

El ensamblado puede mostrar accesos vectoriales a pila, pero contar esos accesos estáticos no prueba su coste dinámico ni que toda la diferencia sea presión de registros. Si umbral128 pierde, no probar una docena de umbrales y presentar el mínimo como holdout. Conservar el negativo y revisar el modelo.

## Vía posterior de mergesort, todavía sin registrar ni ejecutar

Un kernel SIMD que procese varios elementos por decisión podría atacar dependencias y comparación por salida; no basta reemplazar otra rama escalar. Debe mantener el mismo plan/test/buffer para compararlo con std::merge y con el fallido cmov. Antes de medir, demostrar invariante de carry, límites, colas y extremos sin centinelas inválidos. Mezcla vectorial ya tiene antecedentes y no se considera nueva por implementarla aquí. Si el microkernel mejora pero el sorter no, prevalece el resultado completo.
