# Implementación 03 — núcleo empresarial y telemetría de negocio (v0.3.0)

## Objetivo del incremento

Transformar SanoliFood Operations en una aplicación corporativa funcional que
genere actividad legítima, anomalías controlables y evidencia apta para el SOC. El
incremento conserva identidad, RBAC y auditoría de `v0.2.2` y añade procesos de
inventario, producción y calidad sobre PostgreSQL.

## 1. Importar el paquete

Desde PowerShell en Windows:

```powershell
scp "D:\Descargas\SanoliFood_Increment_v0.3.0.zip" socadmin@IP_DE_LA_VM:/home/socadmin/
```

En Ubuntu:

```bash
cd ~/sanolifood-soc
git status --short

IMPORT_DIR="$(mktemp -d)"
unzip -q ~/SanoliFood_Increment_v0.3.0.zip -d "$IMPORT_DIR"
cp -a "$IMPORT_DIR/SanoliFood_Increment_v0.3.0/." .
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh
git diff --stat
```

Antes de continuar, `git status` no debe mostrar cambios previos que no reconozcas.
La importación no incluye `.env` y no sustituye tus secretos.

## 2. Actualizar sin destruir datos

```bash
cd ~/sanolifood-soc
make upgrade-0.3
```

El script realiza, en orden:

1. respaldo `pg_dump` fuera del repositorio;
2. actualización de las variables no secretas;
3. construcción sin caché de `sanolifood/app:0.3.0`;
4. migración Alembic `20260817_0003`;
5. verificación de esquema y healthchecks;
6. 27 pruebas en SQLite aislado.

No uses `docker compose down -v`: el volumen contiene usuarios y auditoría.

Verificación manual adicional:

```bash
docker compose ps
docker compose images
docker compose exec -T app alembic current
docker compose exec -T app python -m sanolifood.schema_guard
make health
make test
```

## 3. Crear identidades operativas

Con el administrador abre **Usuarios** y crea, con contraseñas diferentes:

| Usuario sugerido | Rol |
|---|---|
| `warehouse.operator` | Almacén |
| `production.operator` | Producción |
| `quality.operator` | Calidad |
| `soc.auditor` | Auditor |

No incluyas contraseñas en Git, capturas ni anexos.

## 4. Recorrido funcional reproducible

### 4.1 Inventario

1. Accede como `warehouse.operator`.
2. Abre **Inventario** y comprueba los cuatro ingredientes de demostración.
3. Registra una recepción de `100 kg` de concentrado de tomate con referencia
   `PO-DEMO-001`.
4. Confirma el nuevo saldo y el movimiento en el libro.

### 4.2 Producción

1. Accede como `production.operator`.
2. Planifica `SF26-SAL-0018`, producto Salsa de tomate, cantidad `1000`.
3. Inicia el lote. El sistema descontará `520 kg` de tomate, `85 kg` de azúcar y
   `18 kg` de especias conforme a la receta v1.
4. Envía el lote a Calidad.

Si el material es insuficiente, el lote permanece planificado y ningún consumo se
guarda. Esta propiedad está cubierta por una prueba automatizada.

### 4.3 Calidad

1. Accede como `quality.operator`.
2. Registra pH `4.3`, límites `4.0–4.6`, para `SF26-SAL-0018`.
3. Comprueba el resultado **Conforme** y libera el lote.
4. Para observar una desviación controlada, utiliza otro lote en proceso con pH
   `5.2`; quedará retenido automáticamente.

## 5. Eventos esperados

```text
inventory.movement.recorded
production.lot.created
production.lot.materials_consumed
production.lot.status_changed
quality.check.passed
quality.check.failed
quality.lot.released
```

Comprueba los eventos desde **Auditoría** o sin exponer secretos:

```bash
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select occurred_at,event_type,outcome,actor_username,correlation_id from audit_events order by id desc limit 25;"'
```

## 6. Evidencia BUS-001

```bash
make evidence-business
```

El comando recopila estado, imágenes, healthchecks, migración, esquema, pruebas,
conteos, eventos de negocio y logs en `evidence/BUS-001`.

Capturas recomendadas:

- `dashboard-business-kpis.png`
- `inventory-ledger.png`
- `production-recipes-and-lots.png`
- `quality-deviation-and-hold.png`
- `audit-business-events.png`

Revisa los archivos antes de versionarlos: no deben contener contraseñas, cookies,
tokens CSRF ni `.env`.

## 7. Commit y push

```bash
git status --short
git add .
git commit -m "Tarea: Implementar núcleo empresarial trazable de SanoliFood"
git push
git status
```

## Criterios de finalización

- Tres servicios saludables e imagen `0.3.0`.
- Alembic en `20260817_0003 (head)`.
- 27 pruebas superadas.
- Los cinco roles respetan la separación de funciones.
- Inventario impide saldos negativos.
- Los lotes consumen una receta versionada de manera atómica.
- Las desviaciones retienen lotes y bloquean liberaciones indebidas.
- Eventos de negocio visibles en PostgreSQL y logs JSON.
- Evidencia `BUS-001` completa y repositorio remoto actualizado.
