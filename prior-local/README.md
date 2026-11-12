# SuperSort

Laboratorio CPU de ordenación de enteros. Investigación en curso, sin afirmación de superar el estado del arte.

Notas tipo Obsidian: [mapa](notes/00%20-%20Mapa.md). Protocolo, bibliografía y continuidad viven en notes/.

Requisitos: uv, Python y g++ con C++17. Ejecutar `uv run python run.py --tag piloto`. Los CSV y metadatos se guardan en results/. La reserva auxiliar se incluye en los tiempos y todos los resultados se comparan exactamente con std::sort.

Ejemplo enfocado, Windows:

```powershell
uv run python run.py --sizes 100000 --distributions uniform splitmix --seeds 271 811 1601 --repeats 31 --cpu 2 --algorithms vq simd lsd11 predict_fixed adaptive_fixed --tag mi_experimento --quiet
uv run python analyze.py results/mi_experimento --candidate adaptive_fixed
uv run python status.py
```

El runner conserva las fuentes, cabeceras propias, dependencias directas pequeñas, commits de bibliotecas, flags y datos crudos de cada experimento. Cada etiqueta debe ser nueva. Evitar editar fuentes durante la compilación o ejecutar benchmarks simultáneos.

En Linux añade IPS2Ra e IPS4o secuenciales y necesita TBB/libatomic instalados. Ubuntu local con WSL está disponible en este equipo; sus resultados se comparan entre algoritmos dentro de WSL, por separado de Windows. Los builds viven en carpetas distintas.

Estado y límites: [notas actuales](notes/05%20-%20Estado%20actual.md). Existe una mejora localizada en arrays medianos uniformes; no se ha demostrado superioridad general ni novedad. El selector y los kernels son prototipos de investigación. `profile` es diagnóstico: sus tiempos totales incluyen salida de texto y no sirven para ranking.
