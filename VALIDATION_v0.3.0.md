# Registro de validación — SanoliFood v0.3.0

Fecha de validación: 17 de agosto de 2026.

## Validaciones ejecutadas sobre el paquete

- Compilación de los módulos Python sin errores.
- Validación sintáctica de `entrypoint.sh`, `reset-lab.sh` y
  `upgrade-v0.3.0.sh`.
- Migración completa desde base vacía hasta `20260817_0003 (head)`.
- Comprobación del esquema requerido mediante `sanolifood.schema_guard`.
- Creación del administrador y carga empresarial idempotente ejecutada dos veces.
- Renderizado autenticado de `/`, `/inventory`, `/production`, `/quality` y
  `/audit`, todos con HTTP 200.
- Suite aislada: **27 pruebas superadas**.

## Datos del escenario reproducible verificados

| Entidad | Registros iniciales |
|---|---:|
| Usuarios | 1 |
| Proveedores | 3 |
| Ingredientes | 4 |
| Movimientos de apertura | 4 |
| Productos | 2 |
| Recetas aprobadas | 2 |
| Lotes | 3 |
| Controles de calidad | 2 |

## Invariantes cubiertos por pruebas

- Un movimiento no puede dejar existencias negativas.
- Un lote no se inicia si la receta carece de material suficiente; toda la
  transacción se revierte.
- El inicio del lote descuenta la receta proporcionalmente y emite evidencia.
- Un control fallido retiene automáticamente el lote.
- Un lote con controles fallidos no puede liberarse.
- Almacén, Producción y Calidad no pueden ejecutar operaciones ajenas a su rol.
- `pytest` nunca utiliza la base PostgreSQL operacional.

## Validación pendiente en el host de laboratorio

El entorno de generación no dispone del daemon Docker del usuario. Por ello, la
validación final de Compose debe ejecutarse en Ubuntu con `make upgrade-0.3`. El
script comprueba configuración, imagen, healthchecks, migración, esquema y pruebas
sin borrar el volumen existente. Sus salidas se conservarán como evidencia
`BUS-001`.
