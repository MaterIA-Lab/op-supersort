---
title: Packing varying bits of wide keys into 64-bit sort tags
date: 2026-11-24 00:48
verdict: failed
summary: Packing only varying bits gave nearly identical timings to trimming each field separately. It reached 0.989–1.016× against the fastest reference on four modeled composite-key inputs.
model: GPT-6.2 Sol (Codex, gpt-6.2-sol)
cost: not captured
idea: 10. Pack varying bits of wide keys together with row indices
result: 0.989–1.016× across four primary comparisons
baseline: Fastest verified median of field ranges, leading prefix, high-word key/value pairs and indirect pdqsort
closes: [per-bit compaction on the tested wide-key argsort inputs]
opens: [use field-trimmed tags as a wide-key argsort reference]
speedup: 0.989-1.016
how: Keep the highest bits that differ between rows in a short tag together with the original row number. Sort the tags and consult the full keys only where abbreviated prefixes tie.
compared_with: Tags that trim each field, tags that keep one leading prefix, wider key-and-row-number pairs, and sorting row numbers by comparing the complete keys.
faster_where: With 1.05 and 4.19 million modeled composite keys, the prototype reached 0.989–1.016× against the fastest reference. Trimming fields already gave the same abbreviated keys in those cases. The spatial control had fewer ties with per-bit packing and similar total time.
title_es: Empaquetar los bits variables de claves anchas en etiquetas de 64 bits
how_es: Se guardan los bits más altos que cambian entre registros en una etiqueta corta junto al número de fila. Se ordenan las etiquetas y se consulta la clave completa cuando dos prefijos empatan.
compared_with_es: Etiquetas que recortan cada campo, etiquetas con un solo prefijo, pares más anchos de clave y número de fila, y una ordenación de índices que compara las claves completas.
faster_where_es: Con 1,05 y 4,19 millones de claves compuestas simuladas, el prototipo obtuvo entre 0,989× y 1,016× frente a la mejor referencia. Recortar cada campo ya producía las mismas etiquetas en esas pruebas. En el control espacial hubo menos empates y el tiempo total fue parecido.
---

# Packing varying bits of wide keys into 64-bit sort tags

**Decision. Close per-bit compaction for the tested shapes.** On all four
primary inputs, trimming the range of each 32-bit field already produced
the same tags. Retaining a single contiguous prefix was much slower on
these keys. Include field trimming in future comparisons.
[Registered inputs and stopping rule](protocol.md) · [Prototype and reproduction](../../prototypes/agents/varying-bit-argsort/README.md)

## Timings

Each method constructs an exact, stable permutation of immutable two-word
unsigned keys. The returned array contains a 32-bit source index for
each row. Times include allocation, tag construction, SIMD or comparison
sorting, tie repair, and releasing scratch. The underlying records stay
at their source addresses. Take the median of five calls for each
method and input after two warm-ups. The ratio divides the fastest
reference median by the prototype median.

| Shape | Input | Seed | Varying bits, ms | Field ranges, ms | Leading prefix, ms | Ratio versus best |
|---|---:|---:|---:|---:|---:|---:|
| Composite | 16 MiB | 49331 | 15.747 | 16.001 | 52.679 | 1.016× |
| Composite | 16 MiB | 93817 | 15.948 | 16.101 | 52.215 | 1.010× |
| Composite | 64 MiB | 49331 | 71.204 | 72.262 | 190.371 | 1.015× |
| Composite | 64 MiB | 93817 | 69.824 | 69.041 | 193.504 | 0.989× |
| Morton and time | 16 MiB | 49331 | 15.547 | 15.717 | 43.117 | 1.011× |
| Morton and time | 16 MiB | 93817 | 15.272 | 15.230 | 42.457 | 0.997× |
| Uniform | 16 MiB | 49331 | 15.836 | 15.616 | 15.620 | 0.986× |
| Uniform | 16 MiB | 93817 | 15.896 | 15.613 | 15.709 | 0.982× |

Field ranges had the lowest reference median in every cell. All eight
comparisons missed the 77% time gate. The predefined holdout required a
pass in every primary cell.
[Raw timings](development.csv) · [Every method's medians and geometry](summary.json)

## Why the strongest reference caught up

- **Composite keys.** Tenant and sensor each occupy a contiguous range
  in their own 32-bit field. For the time interval used, the highest
  potentially changing timestamp bit is bit 39. The measured count of
  56 varying bits was the maximum given those fields, so every possible
  varying bit was present and the two masks matched. The two methods
  repaired 0–2 indices at 1.05 million rows and 40–50 at 4.19 million.
  The contiguous prefix repaired every index on those inputs. Field
  trimming ran 2.63–3.29× as fast as that control.
- **Morton and time.** Some constant bits lie inside the significant
  range of a 32-bit field. Per-bit packing reduced the number of indices
  repaired from 18–30 to 0–2. The remaining groups had only two indices
  each, with similar total time at this scale.
- **Uniform keys.** Every bit varied and all three tag methods repaired
  zero indices on both seeds. Per-bit packing put the same information
  into its tags as a leading prefix on these inputs.

The result distinguishes the observed benefit of preserving informative
bits across fields from the extra precision of individual bit selection.
Key normalization and abbreviated prefixes have precedent. Priority for
the exact per-bit selection remains unconfirmed.
[Related work and mechanism](../../notes/ideas.md#10-pack-varying-bits-of-wide-keys-together-with-row-indices)

## Verification and accounting

- All 200 measured calls and 80 warm-ups matched the full permutation
  from a separate stable sort. A preflight also checked 5,506 exhaustive
  and constructed fixtures with all five methods. [Verification log](verification.txt)
- One pinned thread on an AMD Ryzen 7 5800X with Windows 11. Builds
  used GCC 16.1.0 for Zen 3, AVX2 and BMI2. The benchmark flushed input
  cache lines before each timing call. The metadata pins the reference
  versions, compiler flags, source digests and executable digest.
  [Environment and build](development-metadata.json)
- All three packed-tag methods requested 8 bytes of scratch per input
  row. High-word key/value pairs requested 16. Both figures exclude
  allocator overhead, sorter stack and the common 4-byte returned index.
  Peak process memory was not measured.
- Model `gpt-6.2-sol`. External paid compute spend was zero. Model
  tokens, reasoning setting and session cost were not captured.
