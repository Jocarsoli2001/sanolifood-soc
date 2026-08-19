# Implementación 04 — Wazuh central y telemetría SanoliFood

## 1. Alcance

Esta fase cubre las puertas C1, C5 y C6 del plan Wazuh:

| Puerta | Criterio | Estado al finalizar |
|---|---|---|
| C1 | Manager, indexer y dashboard saludables | Completo |
| C2 | Endpoint Ubuntu registrado | Siguiente incremento |
| C3 | FIM sobre configuración de Calidad | Siguiente incremento |
| C4 | Recolección de autenticación Linux | Siguiente incremento |
| C5 | Eventos JSON SanoliFood con actor, IP y correlación | Completo |
| C6 | Reglas locales validadas con `wazuh-logtest` | Completo |
| C7 | Alerta de ataque exportada y mapeada a MITRE | Parcial; se completa con escenarios |

## 2. Arquitectura

La aplicación y Wazuh mantienen ciclos de vida separados. El volumen Docker
`sanolifood_app_logs` contiene `sanolifood.jsonl`. La aplicación escribe una
línea JSON por evento y el manager la abre en modo de solo lectura. El decoder
JSON nativo extrae campos dinámicos como `sf_event_type`, `source_ip`,
`actor_username` y `correlation_id`. El namespace `sf_` evita que la regla
oficial 86600 de Suricata capture telemetría empresarial solo por compartir los
campos genéricos `timestamp` y `event_type`; la decisión se registra en
`docs/adr/ADR-005-telemetry-event-namespace.md`.

Wazuh indexer y API solo son alcanzables desde `sanoli_soc`. El dashboard se
publica en 8443/HTTPS y los endpoints utilizarán 1514/TCP y 1515/TCP. El puerto
514/UDP queda reservado para telemetría syslog posterior de Suricata.

## 3. Transferencia y superposición segura

Desde PowerShell en Windows:

```powershell
scp "D:\Descargas\SanoliFood_Increment_v0.4.0.zip" socadmin@192.168.0.29:/home/socadmin/
```

En Ubuntu, primero confirma que el hito anterior está limpio y después aplica
el paquete sobre el repositorio sin tocar `.git`, `.env` ni los volúmenes:

```bash
cd ~/sanolifood-soc
git status -sb
IMPORT_DIR="$(mktemp -d)"
unzip -q ~/SanoliFood_Increment_v0.4.0.zip -d "$IMPORT_DIR"
cp -a "$IMPORT_DIR/SanoliFood_Increment_v0.4.0/." .
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh wazuh/scripts/*.sh
git status --short
```

El primer estado debe ser `## main...origin/main` sin archivos adicionales. El
segundo debe mostrar únicamente los cambios previstos de v0.4.0. Todavía no
hagas commit.

## 4. Preparación

Mantén apagadas las VMs Kali y Windows durante la primera descarga. En el host
Ubuntu ejecuta:

```bash
cd ~/sanolifood-soc
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh wazuh/scripts/*.sh
make wazuh-preflight
```

La puerta de entrada exige al menos 4 CPU, 8 GiB de RAM, 50 GiB libres y
`vm.max_map_count >= 262144`.

## 5. Actualización segura

```bash
make upgrade-0.4
```

El proceso puede tardar varios minutos en la primera descarga. Crea un respaldo
`sanolifood-pre-v0.4.0-<UTC>.dump`, reconstruye la aplicación, genera secretos y
certificados, descarga las tres imágenes Wazuh y espera sus healthchecks.

No uses durante esta fase:

```text
docker compose down -v
docker volume prune
```

Ambos comandos podrían eliminar datos persistentes y no forman parte del flujo
operativo del laboratorio.

## 6. Acceso

Desde Windows abre:

```text
https://192.168.0.29:8443
```

El navegador mostrará una advertencia porque la CA es propia del laboratorio.
Comprueba la huella del certificado y continúa únicamente hacia la IP de la VM.
Para consultar localmente la contraseña:

```bash
make wazuh-credentials
```

No captures, grabes ni añadas esa salida a Git. El usuario inicial del dashboard
es `admin`.

## 7. Operación diaria

```bash
make wazuh-ps
make wazuh-health
make wazuh-logs
make wazuh-reload-rules # después de editar reglas versionadas
make wazuh-test-rules
make wazuh-down       # conserva volúmenes
make wazuh-up         # arranque idempotente
make soc-health       # aplicación y SOC
```

## 8. Reglas iniciales

| Regla | Nivel | Caso |
|---:|---:|---|
| 110010 | 5 | Fallo individual de autenticación |
| 110011 | 10 | Cinco fallos desde la misma IP en 120 s; MITRE T1110/T1110.001 |
| 110012 | 9 | Cuenta bloqueada |
| 110020 | 8 | Ajuste de inventario de alto valor |
| 110030 | 8 | Control de calidad fuera de especificación |
| 110040 | 12 | Error no controlado de aplicación |

Las reglas de negocio no reciben un mapeo MITRE artificial. Solo la correlación
de autenticación repetida se asocia con Brute Force/Password Guessing.

## 9. Evidencia WAZ-001

Después de provocar al menos un evento empresarial y un fallo de acceso:

```bash
make evidence-wazuh
```

Revisa `evidence/WAZ-001` antes de `git add`. El script no recopila `.env`,
contraseñas ni claves privadas. En tu PC guarda estas capturas:

1. `01-wazuh-containers-healthy.png`: `make soc-health` completo.
2. `02-wazuh-dashboard-overview.png`: página principal sin credenciales visibles.
3. `03-wazuh-manager-status.png`: estado de daemons o Server management/Status.
4. `04-wazuh-ruleset-tests.png`: tres pruebas 110010, 110020 y 110030.
5. `05-sanolifood-alert-threat-hunting.png`: alerta real con regla, actor,
   `source_ip` y `correlation_id`.

El directorio visual recomendado es `WAZ-001/capturas`; los textos reproducibles
pueden permanecer en Git una vez revisados.

## 10. Criterio de salida

No avances al agente Ubuntu hasta que:

```bash
make soc-health
make wazuh-test-rules
make test
git status --short
```

muestre todos los servicios saludables, tres reglas aprobadas, 28 pruebas y
ningún archivo de `wazuh/runtime` preparado para commit.
