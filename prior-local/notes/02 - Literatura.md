# Literatura y referencias

Consulta inicial: 2026-11-04. Fuentes primarias:

- https://github.com/orlp/pdqsort — comparación branchless, referencia incluida.
- https://github.com/skarupke/ska_sort — radix genérico, referencia incluida.
- https://github.com/ips4o — IPS4o y familia IPS2Ra, pendientes de integrar.
- https://github.com/ips4o/ips4o-benchmark-suite — matriz y baselines existentes.
- https://github.com/numpy/x86-simd-sort — SIMD CPU, pendiente de integrar (el 5800X tiene AVX2, no AVX-512).
- https://arxiv.org/abs/2205.05982 — Vectorized and performance-portable Quicksort.
- https://github.com/google/highway/tree/master/hwy/contrib/sort — código vqsort. Integrado después con commit a3f6f68fcc368e5e3025ca25805eabda9d8a456f, despacho estático nativo mediante VQSORT_ONLY_STATIC y HWY_COMPILE_ONLY_STATIC. Interfaz indicada por la propia biblioteca, sin modificar su algoritmo. No se usa OpenMP.
- https://github.com/anikristo/LearnedSort y https://arxiv.org/abs/2107.03290 — aproximar posiciones mediante distribución ya tiene antecedentes.
- https://arxiv.org/abs/2009.13569 — Engineering In-place (Shared-memory) Sorting Algorithms.
- https://www.cs.ucr.edu/~xdong038/files/papers/2024/integer-sort.pdf — Parallel Integer Sort: Theory and Practice, pendiente de lectura detallada.
- https://arxiv.org/abs/2605.25040 — CAFS, versión 2 de 2026-10-19. Leído abstract: ordenación por frecuencia para baja cardinalidad, estimación Chao1 y buckets AVX2. Sus cifras son afirmaciones del autor, no verificadas en nuestro laboratorio. Referencia necesaria si exploramos contar claves distintas.

La división MSD + ordenación local en caché no se considera nueva. El piloto mide si merece optimización en esta máquina. Dependencias descargadas por run.py: los hashes exactos quedan en metadata.json; se conservan cabeceras y avisos de licencia originales en vendor.


Consulta 2026-11-05 para orientación quicksort/mergesort:
- [BlockQuicksort, Edelkamp y Weiß](https://arxiv.org/abs/1604.06697): clasificación por bloques para desacoplar ramas y movimientos; antecedente explícito de Q2.
- [Nearly-Optimal Mergesorts, Munro y Wild](https://arxiv.org/abs/1805.04154): explotar runs y elegir política de mezcla; antecedente explícito de M1.
- [Implementaciones de Powersort/Multiway Powersort](https://github.com/sebawild2/powersort): referencia pendiente de integrar con commit fijado. E036 no basta para afirmar mejora competitiva de mergesort adaptativo.

E037 (2026-11-05): Powersort integrado desde ese repositorio, commit1d078b6be9023e134c4f8f6de88e2406dc681e89. Se usa la implementación binaria por defecto, no4way. Buffer nuevo por llamada, sin reutilizar entre repeticiones. Código/licencia MIT archivados en resultados; supuestos LP64 restringen esta integración a Linux. No se ejecuta el estudio completo upstream.


E040: [GNU ld VERSION](https://sourceware.org/binutils/docs/ld/VERSION.html), consultado2026-11-05: mapa anónimo global:API;local:* limita símbolos visibles del DSO. Se combina con visibilidad oculta/Bsymbolic y verificación readelf de exportaciones definidas para aislar templates de los dos umbrales. No se deduce aislamiento solo de renombrar el wrapper público. La versión privada del x86-simd-sort conserva BSD-3-Clause y fuente original exacta.
