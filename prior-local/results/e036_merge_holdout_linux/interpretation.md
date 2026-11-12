# Interpretación E036

Principal fijo merge_skip. No se sustituye por el control ni se selecciona variante por entrada.

- Frente al control merge_simd: sorted gana8/8, equal6/8; ninguna pérdida>5% en las16 entradas uniform/splitmix. El criterio original incluía ahorro en reverse: no se declara cumplido. La corrección razonada previa al benchmark está en preregistration.md.
- Frente a la mejor referencia externa: pierde120/120. Rechazado como sorter competitivo.
- Frente a std::stable_sort: menor mediana120/120, factores1.005–3.730. El extremo pequeño no demuestra mejora robusta; el prototipo no promete estabilidad con payload. No presentar esto como sustitución de un algoritmo estable.
- Las copias por nivel permanecen aunque se omita mezcla. Es una limitación demostrable del diseño; no se ha perfilado qué fracción de la pérdida corresponde a movimientos, mezcla escalar o hojas.

Próxima hipótesis: evitar niveles mediante runs naturales, con Powersort upstream como referencia y sin cambiar simultáneamente árbol y kernel. Nuevas entradas para validar cualquier cambio.
