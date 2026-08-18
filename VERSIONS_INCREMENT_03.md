# Versiones fijadas — incremento 03

| Componente | Versión |
|---|---:|
| SanoliFood Operations | 0.3.0 |
| Esquema Alembic | 20260817_0003 |
| Python | 3.12.11 |
| FastAPI | 0.116.1 |
| SQLAlchemy | 2.0.43 |
| Alembic | 1.16.5 |
| Psycopg | 3.2.9 |
| PostgreSQL | 17.6-alpine3.22 |
| Nginx | 1.28.0-alpine3.21 |

## Cambios de versión

- `0.3.0`: núcleo empresarial de inventario, producción y calidad.
- Nueva migración `20260817_0003`; conserva las tablas de identidad y auditoría.
- Imagen de aplicación fijada como `sanolifood/app:0.3.0`.
- Datos demostrativos idempotentes habilitados mediante `RUN_DEMO_SEED=true`.
- Suite automatizada ampliada de 16 a 27 pruebas.
