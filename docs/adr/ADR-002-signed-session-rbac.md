# ADR-002 — Sesiones firmadas y RBAC en el monolito modular

- Estado: aceptada
- Fecha: 2026-08-16

## Contexto

SanoliFood necesita autenticación realista, separación de funciones y telemetría de
seguridad sin introducir otro servicio pesado en el equipo de laboratorio.

## Decisión

Se utilizarán sesiones firmadas con cookie `HttpOnly` y `SameSite=Lax`, contraseñas
Argon2id, tokens CSRF y autorización basada en cinco roles. PostgreSQL mantendrá las
identidades y una tabla de auditoría; los mismos sucesos se emitirán como JSON a
stdout para su ingestión posterior en Wazuh.

## Consecuencias

- Se obtiene un flujo de identidad reproducible y suficiente para casos T1110/T1078.
- Nginx continúa siendo el único punto publicado.
- La cookie se marcará `Secure` cuando `APP_ENV=production` y exista HTTPS.
- No se implementa SSO en este alcance; puede añadirse como línea futura.
