# Validación del hotfix v0.2.1

Fecha de validación: 2026-08-17 UTC.

## Resultados locales

- `13 passed` con Pytest.
- Migración desde una base SQLite vacía hasta `20260816_0002 (head)`.
- Creación verificada de `alembic_version`, `platform_metadata`, `users` y
  `audit_events`.
- `schema_guard` acepta el esquema completo y detecta tablas faltantes.
- El login referencia `app.css?v=0.2.1`.
- El CSS contiene las reglas corporativas de `auth-shell` y conserva SHA-256
  `817b681a3daa1a30126625813870ed5cf737f54a03bbc6940ef1b075ccfbc399`.
- `compose.yaml` es YAML válido y utiliza `sanolifood/app:0.2.1`.
- Los scripts de arranque, salud y reinicio superan `bash -n`.

## Validación pendiente en el host del laboratorio

El motor Docker no está disponible en el entorno donde se preparó el paquete.
La prueba integral con PostgreSQL y Nginx se ejecuta automáticamente en Ubuntu
mediante:

```bash
./infrastructure/scripts/reset-lab.sh --confirm
```

La ejecución no se considera cerrada hasta que los tres contenedores aparezcan
saludables y las trece pruebas terminen correctamente en la VM.
