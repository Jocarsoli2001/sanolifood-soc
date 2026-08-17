# Versiones — Incremento 02

| Componente | Versión |
|---|---:|
| SanoliFood Operations | 0.2.2 |
| Python | 3.12.11 |
| FastAPI | 0.116.1 |
| SQLAlchemy | 2.0.43 |
| Alembic | 1.16.5 |
| argon2-cffi | 25.1.0 |
| itsdangerous | 2.2.0 |
| PostgreSQL | 17.6 |
| Nginx | 1.28.0 |

## Hotfix 0.2.1

- La imagen de aplicación se etiqueta como `sanolifood/app:0.2.1`.
- El CSS y JavaScript utilizan URLs versionadas.
- Los assets no se almacenan en caché en `development` y `test`.
- El arranque comprueba que Alembic haya creado todas las tablas requeridas.
- El healthcheck de Nginx valida también el upstream de FastAPI.
- La reconstrucción limpia recrea el stack completo, evitando estados e IPs mezclados.

## Hotfix 0.2.2

- Pytest fuerza una base SQLite en memoria y rechaza cualquier URL de prueba no SQLite.
- `make test` y `reset-lab.sh` omiten el entrypoint operativo y aíslan la ejecución.
- El entrypoint también intercepta invocaciones manuales de pytest y fuerza SQLite.
- `/health/ready` comprueba la presencia de las tablas requeridas.
- La reconstrucción vuelve a validar PostgreSQL después de ejecutar las pruebas.
- Se añade una regresión que demuestra que el motor de pruebas es SQLite.
