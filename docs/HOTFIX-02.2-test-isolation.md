# Hotfix 0.2.2 — aislamiento de pruebas y readiness de esquema

## Causa raíz

La configuración de pytest usaba `os.environ.setdefault("DATABASE_URL", ...)`.
Al ejecutar las pruebas desde Docker Compose, la variable ya contenía la URL de
PostgreSQL del laboratorio. Las fixtures creaban y eliminaban tablas sobre esa
base real. El endpoint de readiness solo ejecutaba `SELECT 1`, por lo que la
plataforma podía declararse saludable aunque faltaran tablas de negocio.

## Correcciones

1. Pytest fuerza una URL SQLite aislada antes de importar la aplicación.
2. Se rechaza cualquier `SANOLIFOOD_TEST_DATABASE_URL` que no sea SQLite.
3. Los comandos de pruebas omiten el entrypoint operativo del contenedor.
4. El propio entrypoint intercepta invocaciones manuales de pytest y fuerza SQLite.
5. `/health/ready` valida conectividad y tablas requeridas.
6. El reset verifica nuevamente el esquema y la salud después de pytest.

## Recuperación recomendada

El estado actual no contiene datos útiles y conserva una revisión Alembic que
ya no coincide con las tablas físicas. Por ello debe importarse este paquete y
ejecutarse una única reconstrucción limpia:

```bash
cd ~/sanolifood-soc
IMPORT_DIR="$(mktemp -d)"
unzip -q ~/SanoliFood_Increment_v0.2.2.zip -d "$IMPORT_DIR"
cp -a "$IMPORT_DIR/SanoliFood_Increment_v0.2.2/." .
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh
./infrastructure/scripts/reset-lab.sh --confirm
```

El reset elimina únicamente los recursos declarados por el proyecto Compose
`sanolifood`, regenera las credenciales locales y reconstruye PostgreSQL desde
las migraciones.

## Criterios de aceptación

```bash
docker compose images
docker compose ps
make health
make test
docker compose exec -T app python -m sanolifood.schema_guard
make health
```

Resultados esperados:

- Imagen `sanolifood/app:0.2.2`.
- Tres servicios en estado `healthy`.
- Dieciséis pruebas aprobadas.
- Evento `database_schema_verified` después de pytest.
- El segundo `make health` también finaliza correctamente.
