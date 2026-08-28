# Plataforma SOAR SanoliFood v0.7.0

Este directorio implementa una capa SOAR semiautomatizada. n8n orquesta los
flujos, mientras un controlador FastAPI conserva incidentes, acciones,
auditoría y métricas en PostgreSQL. Las decisiones de contención nunca dependen
del estado efímero de una ejecución de n8n.

## Recorrido de una alerta

1. Wazuh ejecuta `custom-sanolifood-soar` solo para las reglas incluidas en el
   catálogo.
2. El integrador envía un sobre JSON firmado con HMAC-SHA256 al webhook interno
   de n8n.
3. n8n valida firma y antigüedad, normaliza la alerta, deduplica y selecciona un
   playbook versionado.
4. El controlador crea el incidente y ejecuta la conservación automática de
   evidencia.
5. Las acciones con impacto quedan en `pending_approval`.
6. El analista aprueba o rechaza mediante el cliente local autenticado.
7. En `dry-run` se simula la respuesta. En `live` la aplicación aplica el
   control temporal y devuelve su fecha de caducidad.
8. El flujo de expiración ejecuta rollback; también puede solicitarse antes de
   la caducidad.

## Servicios

| Servicio | Responsabilidad | Persistencia |
|---|---|---|
| `n8n` | Webhooks, validación, triage y coordinación | `sanolifood_n8n_data` y PostgreSQL |
| `soar-controller` | Casos, acciones, idempotencia, auditoría y métricas | Base PostgreSQL `soar` |
| `soar-db` | Bases separadas para n8n y el controlador | `sanolifood_soar_db_data` |
| aplicación | Adaptadores de contención empresarial | Tabla `soar_controls` |

El controlador solo publica `5680` en `127.0.0.1`. Wazuh alcanza n8n mediante
la red interna `sanoli_soar`; PostgreSQL y el controlador viven en una segunda
red `sanoli_soar_backend` a la que el manager no pertenece. No se envían
alertas por Internet. La red puente `sanoli_soar_host` existe únicamente para
que Docker publique `5678` y `5680` en loopback; mitiga el comportamiento de
Docker Engine 29.x que descarta los puertos de contenedores conectados solo a
redes `internal`. Las comunicaciones operativas permanecen en las redes
privadas y ninguna interfaz del laboratorio publica esos puertos.

Dentro del contenedor, n8n escucha en `0.0.0.0` mediante
`N8N_LISTEN_ADDRESS`; esto no lo expone en el host. La publicación de Docker
continúa limitada a `127.0.0.1`, y `N8N_HOST` solo define la dirección anunciada
por el editor. El healthcheck usa el alias `n8n` para comprobar la interfaz del
contenedor y evitar que una escucha exclusiva en loopback produzca un estado
saludable falso.

## Workflows versionados

| Archivo | Función |
|---|---|
| `00-error-handler.json` | Persiste errores de cualquier flujo |
| `01-alert-intake.json` | Verifica HMAC, normaliza, deduplica y crea el caso |
| `02-analyst-decision.json` | Verifica la decisión y despacha acciones aprobadas |
| `03-expiration-rollback.json` | Revierte cada minuto los controles caducados |
| `04-health-metrics.json` | Verifica salud y actualiza métricas operativas |

Los nodos HTTP tienen tres intentos acotados. El identificador de incidente y
el `action_id` estable hacen seguros los reintentos frente a entregas repetidas.
Una acción que agote sus intentos puede reintentarse manualmente hasta cinco
veces sin generar un control duplicado.

## Respuestas disponibles

| Adaptador | Efecto | Protección |
|---|---|---|
| `collect_evidence` | Materializa alerta y contexto normalizado | Automático, sin contención |
| `app_ip_block` | Rechaza temporalmente peticiones de una IP | CIDR permitido y lista de IP protegidas |
| `app_account_lock` | Impide temporalmente iniciar sesión | Formato estricto y usuarios protegidos |
| `quality_guard` | Suspende liberaciones de lotes | Objetivo fijo `quality-release` |

Para añadir otra respuesta se incorpora un adaptador en el controlador, su
validación de destino y una entrada en `config/playbooks.json`. La validación
estática impide publicar catálogos distintos entre n8n, Wazuh y el controlador.

## Despliegue seguro

Si parte del hito `v0.6.0`, utilice el upgrade integrado:

```bash
make upgrade-0.7
```

Antes de migrar, el comando crea automáticamente un respaldo PostgreSQL en el
directorio hermano `sanolifood-backups/`. Después deja n8n en `dry-run` y el
reenvío de Wazuh deshabilitado hasta publicar correctamente los cinco flujos.

```bash
make soar-static-check
make soar-preflight
make soar-up
```

El editor solo se enlaza a loopback. Desde el equipo de administración cree un
túnel SSH, mantenga esa consola abierta y visite `http://127.0.0.1:5678`:

```bash
ssh -L 5678:127.0.0.1:5678 socadmin@IP_DE_UBUNTU
```

Cree la cuenta propietaria local de n8n y cierre la sesión. Después publique
los flujos desde Ubuntu:

```bash
make soar-install-workflows
make soar-health
make soar-validate-live
```

Wazuh permanece desconectado de n8n hasta que todos los flujos se importan,
publican y pasan el healthcheck. La primera validación debe devolver
`response_mode: dry-run` y `containment_status: simulated`.

## Operación del analista

```bash
make soar-incidents
make soar-show INCIDENT_ID=UUID

make soar-approve \
  INCIDENT_ID=UUID \
  ANALYST=soc.analyst \
  REASON='Origen verificado y contención temporal autorizada'

make soar-reject \
  INCIDENT_ID=UUID \
  ANALYST=soc.analyst \
  REASON='Actividad legítima confirmada durante la revisión'

make soar-rollback ACTION_ID=UUID ANALYST=soc.analyst
make soar-retry ACTION_ID=UUID ANALYST=soc.analyst
make soar-metrics
```

Las decisiones exigen identidad y justificación. Los webhooks del analista
también se firman y aceptan únicamente solicitudes de los últimos cinco
minutos.

## Activación de respuestas reales

No edite el modo mientras haya una validación en curso. Primero complete la
prueba en seco y revise `n8n/runtime/.env`:

```bash
make soar-validate-live
make soar-enable-live CONFIRM=live
make soar-validate-live
```

La segunda validación aplica un bloqueo sobre `10.20.0.50` y lo revierte dentro
de la misma prueba. Para volver inmediatamente a simulación:

```bash
make soar-disable-live
```

Cambiar a `dry-run` no abandona controles previos: el flujo de expiración sigue
revirtiendo las acciones que ya estaban aplicadas.

## Respaldo, apagado y evidencia

```bash
make soar-backup
make evidence-soar
make soar-disable-integration
make soar-down
```

El respaldo queda en `backups/soar/`, contiene las bases, secretos y la clave de
cifrado de n8n en un directorio de permisos restrictivos y está excluido de Git.
Debe guardarse con control de acceso. `make soar-down`
deshabilita el reenvío de Wazuh antes de detener n8n para evitar entregas a un
webhook ausente.

## Datos que nunca deben publicarse

- `n8n/runtime/.env` y `n8n/runtime/secrets/`;
- el respaldo de PostgreSQL;
- cookies o credenciales de la cuenta propietaria de n8n;
- claves HMAC o `SOAR_INTERNAL_TOKEN`;
- capturas donde aparezcan esas credenciales.
