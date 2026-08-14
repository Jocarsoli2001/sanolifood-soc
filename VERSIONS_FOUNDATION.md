# Versiones del incremento base

Fecha de validación prevista: 2026-08-13.

| Componente | Versión fijada | Uso |
|---|---:|---|
| Python | 3.12.11 | Runtime de la aplicación |
| FastAPI | 0.116.1 | Web y API |
| Uvicorn | 0.35.0 | Servidor ASGI |
| SQLAlchemy | 2.0.43 | ORM y transacciones |
| Alembic | 1.16.5 | Migraciones |
| Psycopg | 3.2.9 | Driver PostgreSQL |
| Pydantic Settings | 2.10.1 | Configuración |
| Jinja2 | 3.1.6 | Plantillas HTML |
| PostgreSQL | 17.6-alpine3.22 | Base de datos |
| Nginx | 1.28.0-alpine3.21 | Reverse proxy |

Antes de congelar `v0.1-app`, registrar también los identificadores de imagen obtenidos con
`docker image inspect` y conservar la salida de `docker compose images`.

