# Continuidad de SuperSort

El usuario solicita investigación sostenida de sorting CPU, mejoras prácticas verificadas y notas estilo Obsidian. Leer notes/00 - Mapa.md y notes/04 - Reanudar.md antes de continuar.

- No afirmar que se supera el estado del arte por ganar a std::sort o a nuestros propios radix.
- CPU exclusivamente. Primera fase uint32 sin payload, un hilo. Documentar cambios de contrato.
- Usar uv/Python para orquestar y analizar; kernels nativos para comparar costes reales.
- No ejecutar compilaciones ni otras cargas intensivas simultáneamente con benchmarks.
- Guardar muestras crudas, fuente exacta, entorno y dependencias. Nunca sobreescribir results existentes.
- Comparar resultados exactamente con std::sort fuera del tiempo medido. Incluir reserva y copia final auxiliar.
- No descartar resultados negativos ni seleccionar semillas favorables.
- Actualizar diario y reanudar después de cada etapa. Informar de límites y del siguiente experimento.
- No hay trabajo en ejecución entre turnos salvo un proceso local explícitamente lanzado y seguido. No prometer días de ejecución autónoma tras cerrar un turno.
- Avisar al usuario de puntos de compacción antes de agotar contexto.
