# Validación del hotfix v0.2.2

## Incidente reproducido

- Pytest heredaba `DATABASE_URL` desde Compose.
- Las fixtures destruían las tablas del PostgreSQL operativo.
- `/health/ready` solo comprobaba `SELECT 1` y producía un falso positivo.

## Controles añadidos

- El entorno de pruebas fuerza SQLite en memoria.
- Un test comprueba que el backend efectivo sea `sqlite`.
- Una regresión verifica que readiness responde `503` si falta el esquema.
- El reset ejecuta pytest sin el entrypoint de producción.
- El entrypoint posee una segunda barrera para ejecuciones manuales de pytest.
- El esquema operativo vuelve a validarse después de las pruebas.

## Verificación local del paquete

- Suite automatizada: `16 passed` aun iniciando pytest con una URL PostgreSQL
  señuelo en el entorno; el motor efectivo permaneció en SQLite.
- Migraciones Alembic `20260813_0001` y `20260816_0002` sobre una base vacía.
- Readiness `200` con el esquema completo y regresión `503` sin tablas.
- Guard de esquema aprobado antes y después de ejecutar pytest.
- Usuario bootstrap conservado después de las pruebas (`count(*) = 1`).
- Validación sintáctica de Compose y scripts de shell.
- Comprobación de que no persisten referencias ejecutables a la imagen 0.2.1.

La validación Docker/PostgreSQL final debe ejecutarse en la VM Ubuntu mediante
`./infrastructure/scripts/reset-lab.sh --confirm`.
