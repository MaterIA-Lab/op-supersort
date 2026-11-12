# Selección y ensamblado E039

Binario y hash en bench.bin/binary.json, código completo de ambos ejecutores en merge-assembly.txt.

Ejecutor cmov:0x5b00; comparación/selección0x5b7f/0x5b84 cmovbe y actualización con setae, segunda parte0x5bce/0x5bd1 cmovbe y setbe/seta. Saltos restantes de esta región dependen del agotamiento de índices, no de la selección de claves. Control std::merge compara claves y salta en0x17e9a/0x17e9d. Se cumple el criterio del mecanismo, sin medir contadores de fallos de rama ni ciclos.

Velocidad random mejora marginalmente, robustez falla. En equal el diagnóstico indica C_exec0: no atribuir sus diferencias al kernel que no se llama. No afirmar que todo el tiempo de few se explique exclusivamente por ramas; cadenas de dependencias/cargas y código generado no se han aislado por contadores. Resultados completos en analysis-kernel.md.
