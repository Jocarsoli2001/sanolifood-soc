# SanoliFood SA — Incremento 01: plataforma base v0.1.0

Este paquete implementa el primer incremento ejecutable del portal corporativo de SanoliFood SA.
No contiene todavía autenticación, recetas, lotes ni inventario: establece la arquitectura definitiva
sobre la que se añadirán esos módulos.

## Componentes

- Nginx como único punto publicado en el host.
- FastAPI estructurado como paquete modular.
- PostgreSQL aislado en una red interna.
- Alembic para versionar el esquema.
- Logging JSON con `correlation_id`, latencia, IP y estado HTTP.
- Healthchecks de vida, disponibilidad y proxy.
- Interfaz corporativa offline, sin dependencias CDN.
- Pruebas automáticas de endpoints y middleware.

## Ejecución

1. Copiar el contenido sobre la raíz del repositorio `~/sanolifood-soc`.
2. Crear `.env` a partir de `.env.example` y cambiar las contraseñas de ejemplo.
3. Ejecutar `docker compose config --quiet`.
4. Ejecutar `docker compose up -d --build`.
5. Validar con `make health` y `make test`.

La aplicación se publica por defecto en `http://IP_DE_LA_VM:8080`.

La ejecución guiada, los resultados esperados y la captura de evidencias están en
`docs/IMPLEMENTATION-01-foundation.md`.
