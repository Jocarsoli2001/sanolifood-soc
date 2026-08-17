# SanoliFood SA — Incremento 02: identidad, acceso y auditoría

Este paquete actualiza la plataforma base `v0.1.0` a `v0.2.2` e incorpora:

- Inicio y cierre de sesión con cookie firmada.
- Contraseñas protegidas con Argon2id.
- Protección CSRF en operaciones de escritura.
- Bloqueo temporal tras cinco intentos fallidos.
- Roles de administrador, producción, calidad, almacén y auditor.
- Creación, activación y desactivación de usuarios.
- Auditoría persistente y eventos JSON correlacionados.
- Pantallas corporativas de login, usuarios y auditoría.
- Migración Alembic `20260816_0002`.
- Dieciséis pruebas automáticas ejecutadas exclusivamente en SQLite aislado.
- Assets estáticos versionados y sin caché durante el desarrollo.
- Validación de integridad del esquema antes del bootstrap.
- Reconstrucción limpia y acotada mediante `make reset-lab`.
- Readiness sensible a tablas ausentes, no solo a conectividad SQL.
- Verificación posterior a pytest para impedir daños silenciosos en PostgreSQL.
- Protección adicional en el entrypoint para invocaciones manuales de pytest.

La guía ejecutable vigente está en `docs/HOTFIX-02.2-test-isolation.md`.
