# Dependencia Python de la Parte A

`e042_work.py` importó `quick_support.py` para SHA256 de archivos/árboles y comprobación de exportaciones ELF. El manifiesto inicial no incluyó este módulo en `frozen_inputs`. La copia actual coincide byte por byte con la copia de E040 y con la copia retenida en la recuperación de sanitizadores, SHA256 `02e3709c42836205c977bc7a0ee52366ef739518b01cb614b298280366df959e`. Esta comprobación posterior completa la identificación del módulo disponible. El hash no fue recogido por el orquestador inicial antes/después de compilar.

- [Copia de E040](../e040_quick_holdout_linux/quick_support.py)
- [Copia de la recuperación](../e042_sanitizer_recovery/quick_support.py)
