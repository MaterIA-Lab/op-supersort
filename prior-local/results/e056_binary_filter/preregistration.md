# E056 — Dos particiones binarias para una ventana densa

## Hipótesis y puerta

Separar clasificación y conteo evita enumerar las máscaras de internos e intercalar actualizaciones dispersas del histograma con escrituras a dos extremos, como en E049. Una partición SIMD de Highway separa primero las claves por encima de la ventana. Una segunda partición sobre el prefijo restante separa las inferiores. El tramo central ya es contiguo y se cuenta sin ramas por pertenencia. El control conserva el reparto fusionado de E049. Ambos ordenan con vqsort los dos tramos externos y emiten los mismos contadores en el centro. Se usa primero el límite alto porque en `mixed` el intervalo de valores por encima de la ventana es más amplio. Es un orden fijo para todas las entradas.

La variante paga una segunda partición parcial y otra lectura del tramo central, además de escribir las claves internas durante el reparto. `dense16` fuerza dos particiones casi completas. `late_miss` coloca todas las muestras en una ventana que contiene solo esas 256 claves, y concentra las demás en otro prefijo. Penaliza el coste de una propuesta engañosa y deja un solo extremo para ordenar. Se incluyen `uniform` y `prefix_distinct` como controles de bypass.

La puerta exige que ambas semillas de `mixed` recorran la ruta de ventana en los dos brazos, que `mediana(vq)/mediana(binary) ≥ 1,25` y que `mediana(split)/mediana(binary) > 1` en cada semilla. Cualquier fallo descarta la implementación y cierra el filtro. Los controles se publican completos. Si pasa, repetir con vqsort, x86-simd-sort e IPS2Ra en la misma tanda antes de evaluar una integración.

## Protocolo y correctitud

Ubuntu WSL, CPU lógica 2, GCC con `-O3 -march=native -DNDEBUG -std=c++17` y Highway estático fijado como en E055. 10M claves, semillas `42701` y `91009`, un calentamiento y siete muestras por caso y brazo. Generadores de E054 para `mixed`, `uniform`, `prefix_distinct` y `dense16`. Orden permutado y mismo estado inicial de vqsort antes de cada brazo de una ronda.

En los dos brazos de ventana se cobran el mismo probe y la misma reserva inicializada de 65.536 contadores. El probe busca al menos 96 coincidencias de prefijo en las 256 muestras estratificadas habituales. Sin propuesta, fuera del rango de tamaño del probe o si se rechaza la reserva se ejecuta vqsort. Tras aceptar la propuesta, cualquier partición es exacta para ese intervalo aunque la muestra sobreestime su población. Se cobran los dos ordenados de extremos y la emisión. El pivote alto es inclusivo. El bajo se construye restando uno al primer valor interno solo si este es distinto de cero. Se omite el corte que vaciaría un lado por el límite del dominio. La salida vuelve al array original sin buffer de claves.

Fuera del reloj quedan la generación, la copia común, la referencia `std::sort` y la comparación exacta. Antes de medir se verifican la partición aislada con pivotes extremos y no alineados, tamaños pequeños y colas, guardas y offsets, tamaños de admisión, ventanas en los extremos del dominio, multiplicidades y propuestas engañosas. Se conservan muestras, fuente exacta, entorno, binario y dependencias en un directorio nuevo.
