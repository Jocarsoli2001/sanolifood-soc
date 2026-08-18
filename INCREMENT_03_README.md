# SanoliFood Operations v0.3.0 — núcleo empresarial trazable

Este paquete actualiza la plataforma estable `v0.2.2` sin eliminar PostgreSQL ni
las identidades existentes. Incorpora tres módulos empresariales funcionales:

- **Inventario:** proveedores, ingredientes, puntos de reposición y movimientos
  atómicos con prevención de existencias negativas.
- **Producción:** productos, recetas versionadas, lotes y consumo automático de
  materiales al iniciar fabricación.
- **Calidad:** controles contra límites, retención automática por desviaciones y
  liberación o rechazo segregados por rol.

Cada acción relevante persiste un evento de auditoría y se emite como JSON con
`correlation_id`. Esto convierte la aplicación en una fuente real de telemetría
para Wazuh, Suricata y n8n, no en una interfaz aislada del laboratorio SOC.

## Actualización recomendada desde v0.2.2

Después de copiar el contenido del paquete sobre `~/sanolifood-soc`, ejecuta:

```bash
cd ~/sanolifood-soc
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh
make upgrade-0.3
```

El proceso crea un respaldo fuera del repositorio, actualiza `.env`, construye la
imagen `sanolifood/app:0.3.0`, aplica `20260817_0003`, espera los healthchecks y
ejecuta 27 pruebas en SQLite aislado. **No utiliza `down -v`.**

Resultado esperado:

```text
20260817_0003 (head)
27 passed
OK   postgres     state=running health=healthy
OK   app          state=running health=healthy
OK   nginx        state=running health=healthy
OK   HTTP         http://127.0.0.1:8080/health/ready
```

La guía completa está en `docs/IMPLEMENTATION-03-business-core.md`.

## Roles y separación de funciones

| Rol | Inventario | Producción | Calidad | Auditoría |
|---|---|---|---|---|
| Administrador | lectura/escritura | lectura/escritura | lectura/decisión | lectura |
| Almacén | lectura/escritura | lectura | lectura | sin acceso |
| Producción | lectura | lectura/escritura | lectura | sin acceso |
| Calidad | lectura | consulta/aprobación de receta | lectura/decisión | sin acceso |
| Auditor | lectura | lectura | lectura | lectura |

## Señales listas para ingeniería de detección

| Evento | Significado defensivo |
|---|---|
| `inventory.adjustment.high_value` | Ajuste de inventario de magnitud igual o superior a 100 unidades |
| `production.lot.materials_consumed` | Consumo automático asociado a lote y versión de receta |
| `production.lot.status_changed` | Cambio trazable del ciclo de vida de un lote |
| `quality.check.failed` | Parámetro fuera de especificación y retención automática |
| `quality.lot.released` / `quality.lot.rejected` | Decisión final segregada de Calidad |

Estas señales se utilizarán en el siguiente incremento para crear decodificadores,
reglas Wazuh y playbooks n8n reproducibles.
