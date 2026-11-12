# E057 — Encadenar dos niveles de unión con bloques en caché

## Hipótesis

Ordenar tramos contiguos de 65.536 claves con vqsort. Combinar cuatro tramos por nivel lógico con tres uniones binarias, y alternar el array de entrada y un buffer de destino de `n` claves entre niveles. El control materializa completos los dos resultados intermedios y después los une. La variante conserva la misma topología, kernel de unión y destino, y genera cada intermedio por bloques reutilizables de 2.048 claves a medida que la unión final los necesita. El cambio elimina las escrituras y lecturas de intermedios grandes y reduce su reserva de `n` claves a dos bloques. Los accesos lógicos a los intermedios permanecen y se espera que una mayor fracción ocurra en caché.

La variante paga recargas y mantiene tres estados de unión activos. Claves intercaladas entre los cuatro orígenes fuerzan mantener ambos productores en marcha y pueden hacer más costosas las recargas. Tramos de valores concentrados o con colas desiguales pueden llevar al kernel a más trabajo escalar. Los dos brazos cobran las reservas, los tramos iniciales, todos los niveles y la copia de vuelta si la salida queda en el auxiliar. Un fallo de reserva delega en vqsort sobre la entrada original. La implementación se contrasta dentro del contrato propio. El paquete público de Origami es un antecedente de árboles residentes en caché y la entrada directa de su sorter no es un brazo de esta tanda.

## Filtro

10M de claves `uint32`, sin payload, un hilo, salida en el array original. Ubuntu WSL, CPU lógica 2, GCC `-O3 -march=native -DNDEBUG -std=c++17`, Highway estático fijado. Generadores de E054 para `uniform`, `prefix_distinct`, `mixed` y `dense16`, semillas `42701` y `91009`. Brazos `bulk`, `stream` y `vq`. Un calentamiento y siete muestras en orden permutado, mismo estado inicial de vqsort por ronda. Cada salida debe coincidir con `std::sort` fuera del tiempo. Verificar previamente longitudes de cola, tramos vacíos y desiguales, guardas, duplicados, extremos y los límites de tamaño de tramo y bloque.

Ampliar solo si `mediana(bulk)/mediana(stream) > 1` y `mediana(vq)/mediana(stream) ≥ 1,25` en las cuatro entradas prioritarias `uniform` y `prefix_distinct`. `mixed` y `dense16` son controles completos. Si solo gana al control, registrar la reducción interna y cerrar la implementación como candidata general. La diferencia de tiempo incluye el cambio de huella y la frecuencia de recarga. No mide por sí sola tráfico de DRAM.

[Antecedente Origami](https://www.vldb.org/pvldb/vol15/p259-arman.pdf). [[14 - Diseño de mezcla SIMD]].
