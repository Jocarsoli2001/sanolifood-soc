# SanoliFood SOC

Laboratorio SOC reproducible para una empresa ficticia de procesamiento de
alimentos. El proyecto integra una aplicación empresarial trazable,
monitorización SIEM, telemetría de red IDS/NDR y reglas de detección
versionadas en un entorno desplegable con Docker Compose.

> Uso autorizado: este repositorio está diseñado exclusivamente para un
> laboratorio propio, aislado y controlado. No ejecute las validaciones de
> seguridad contra sistemas o redes de terceros.

## Estado del proyecto

El incremento técnico en curso es **SanoliFood SOC v0.8.0**. La aplicación y el
plano SOAR conservan la versión **0.7.0**; el nuevo hito añade una capa de
evaluación atribuible sin modificar sus datos ni controles operativos.

| Capacidad | Estado | Validación reproducible |
|---|---|---|
| Aplicación SanoliFood Operations | Operativa | Healthchecks, migraciones y 39 pruebas |
| Identidad, sesiones, RBAC y auditoría | Operativa | Cinco roles y eventos correlacionados |
| Inventario, producción y calidad | Operativa | Recorrido empresarial de extremo a extremo |
| Wazuh manager, indexer y dashboard | Operativo | Healthchecks y reglas probadas con `wazuh-logtest` |
| Suricata IDS/NDR | Operativo | EVE JSON, reglas locales y alerta real en Wazuh |
| Agentes Wazuh en endpoints | Implementado | Ubuntu, Windows, Sysmon, FIM y pruebas en vivo |
| Automatización semiautomatizada con n8n | Implementada | Cinco workflows, nueve playbooks y validación E2E |
| Campaña completa de escenarios y métricas | Framework implementado | Ocho recorridos con marcador único y resultados aislados |

Los elementos pendientes se mantienen visibles deliberadamente: el repositorio
no presenta como implementada una capacidad que todavía no ha sido validada.

## Índice

- [Objetivo](#objetivo)
- [Arquitectura](#arquitectura)
- [Capacidades de la aplicación](#capacidades-de-la-aplicación)
- [Requisitos](#requisitos)
- [Instalación desde cero](#instalación-desde-cero)
- [Recorrido funcional](#recorrido-funcional-de-verificación)
- [Ingeniería de detección](#ingeniería-de-detección)
- [Validación NDR en vivo](#validación-ndr-en-vivo)
- [Despliegue de endpoints](#despliegue-de-endpoints)
- [Validación EDR en vivo](#validación-edr-en-vivo)
- [Respuesta SOAR con n8n](#respuesta-soar-con-n8n)
- [Campaña final de evaluación](#campaña-final-de-evaluación)
- [Evidencias y validación](#evidencias-y-validación)
- [Operación diaria](#operación-diaria)
- [Resolución de problemas](#resolución-de-problemas)
- [Reproducibilidad](#reproducibilidad)
- [Hoja de ruta](#hoja-de-ruta)

## Objetivo

El laboratorio demuestra un flujo defensivo completo y medible:

1. actividad empresarial o simulación controlada;
2. generación de telemetría de aplicación o red;
3. ingestión y normalización de eventos;
4. detección mediante reglas deterministas;
5. investigación en Wazuh;
6. conservación de evidencia reproducible;
7. respuesta semiautomatizada, reversible y medible con aprobación humana.

El caso de estudio representa a **SanoliFood SA**, una organización ficticia
que administra ingredientes, recetas, lotes de producción, controles de calidad
y decisiones de liberación. Todos los datos incluidos son sintéticos; el
proyecto no depende de datos personales ni de información empresarial real.

## Arquitectura

```mermaid
flowchart TD
    C["Kali / cliente de prueba<br/>10.20.0.30"] -->|HTTP 8080| N["Nginx<br/>10.20.0.10"]
    C -->|Tráfico observado| S["Suricata IDS/NDR<br/>enp0s8"]
    N --> A["FastAPI<br/>SanoliFood Operations"]
    A --> P["PostgreSQL<br/>datos transaccionales"]
    A -->|JSONL| W["Wazuh manager"]
    S -->|EVE JSON| W
    U["Ubuntu endpoint<br/>10.20.0.10"] -->|Agente 1514/TCP| W
    X["Windows + Sysmon<br/>10.20.0.20"] -->|Agente 1514/TCP| W
    W --> I["Wazuh indexer"]
    I --> D["Wazuh dashboard<br/>HTTPS 8443"]
    W -->|"JSON firmado"| O["n8n<br/>orquestación SOAR"]
    O --> R["Controlador<br/>casos y métricas"]
    R -->|"control aprobado"| A
    R --> Q[("PostgreSQL SOAR")]
```

La aplicación y el SOC conservan ciclos de vida separados. Los volúmenes
`sanolifood_app_logs` y `sanolifood_suricata_logs` conectan las fuentes de
telemetría con Wazuh en modo de solo lectura. PostgreSQL, FastAPI y Nginx se
segmentan mediante las redes `sanoli_data`, `sanoli_app` y `sanoli_dmz`.

### Componentes versionados

| Componente | Versión fijada | Función |
|---|---:|---|
| Ubuntu Server | 24.04 LTS | Host Linux del laboratorio |
| Docker Engine / Compose | Compose v2 | Despliegue reproducible |
| Python | 3.12.11 | Runtime de la aplicación |
| FastAPI | 0.116.1 | Aplicación web y API |
| PostgreSQL | 17.6 | Persistencia transaccional |
| Nginx | 1.28.0 | Punto de entrada y proxy inverso |
| Wazuh | 4.14.7 | SIEM, análisis, indexación y dashboard |
| Wazuh Agent | 4.14.7 | Telemetría EDR de Ubuntu y Windows |
| Suricata | 8.0.6 | IDS/NDR y generación de EVE JSON |
| Sysmon | 15.21 | Telemetría avanzada de Windows con configuración versionada |
| n8n | 2.36.7 | Orquestación, aprobación, caducidad y recuperación de errores |

### Puertos publicados

| Puerto | Protocolo | Servicio | Exposición prevista |
|---:|---|---|---|
| 8080 | TCP/HTTP | SanoliFood Operations mediante Nginx | Red del laboratorio |
| 8443 | TCP/HTTPS | Wazuh Dashboard | Red del laboratorio |
| 1514 | TCP | Eventos de agentes Wazuh | Segmento interno `10.20.0.0/24` |
| 1515 | TCP | Enrolamiento de agentes Wazuh | Segmento interno `10.20.0.0/24` |
| 514 | UDP | Entrada syslog reservada | Fuentes futuras |
| 5678 | TCP/HTTP | Editor y webhooks de n8n | Solo `127.0.0.1`; acceso administrativo por túnel SSH |
| 5680 | TCP/HTTP | API del controlador SOAR | Solo `127.0.0.1` |

El indexer y la API interna de Wazuh no se publican en el host.

## Capacidades de la aplicación

### Módulos empresariales

- **Inventario:** ingredientes, proveedores, recepciones, ajustes y libro de
  movimientos; impide saldos negativos.
- **Producción:** recetas versionadas, planificación de lotes, consumo atómico de
  materiales y transiciones de estado.
- **Calidad:** controles con límites, resultados conforme/no conforme, retención
  y liberación de lotes.
- **Gobierno:** usuarios, roles, sesiones firmadas, bloqueo por intentos fallidos
  y auditoría de acciones.
- **Observabilidad:** eventos JSON estructurados con actor, IP de origen,
  resultado e identificador de correlación.

### Separación de funciones

| Rol | Capacidades principales |
|---|---|
| `admin` | Administración de usuarios y acceso completo |
| `warehouse` | Recepciones y movimientos de inventario |
| `production` | Planificación y ejecución de lotes |
| `quality` | Controles, retenciones y liberaciones |
| `auditor` | Consulta de evidencia y eventos |

## Estructura del repositorio

```text
.
├── app/                 Aplicación, migraciones, plantillas y pruebas
├── infrastructure/      Nginx y scripts operativos
├── wazuh/               Compose, configuración, reglas y pruebas SIEM
├── suricata/            Sensor, firmas y scripts IDS/NDR
├── endpoints/           Agentes, políticas centralizadas, Sysmon y validaciones
├── evidence/            Evidencia textual revisada y no secreta
├── docs/adr/             Decisiones de arquitectura
├── detections/          Espacio para casos de detección adicionales
├── evaluation/          Catálogo, orquestador, métricas y evidencia final
├── n8n/                 Compose, workflows, playbooks y operación SOAR
├── scenarios/           Estímulos acotados para Kali y negocio
├── compose.yaml         Plataforma empresarial
├── Makefile             Interfaz operativa común
└── CHANGELOG.md         Evolución pública del proyecto
```

Los archivos de `wazuh/runtime/` y `suricata/runtime/` son generados localmente,
contienen secretos o datos específicos del host y están excluidos de Git.

## Requisitos

### Host recomendado

- Ubuntu Server 24.04 LTS ejecutado en hardware físico o en una VM.
- 4 vCPU como mínimo.
- 8 GiB de RAM como mínimo; 10–12 GiB recomendados para mayor fluidez.
- 50 GiB libres como mínimo; 80 GiB recomendados para conservar evidencias.
- Una VM Windows 10/11 con 2 vCPU y 4 GiB de RAM recomendados.
- Una red interna aislada entre Ubuntu, Windows y la VM Kali.

Los preflight checks de Wazuh exigen 4 CPU, 8 GiB de RAM, 50 GiB libres y
`vm.max_map_count >= 262144`. Suricata requiere un host Linux porque utiliza el
namespace de red del host y capacidades de captura de paquetes.

### Software del host

```bash
sudo apt update
sudo apt install -y git make curl openssl iproute2 ca-certificates openssh-client
docker --version
docker compose version
git --version
```

Docker Engine y el complemento Docker Compose deben estar instalados y el
usuario del laboratorio debe poder ejecutar `docker` sin `sudo`. Siga la
documentación oficial de Docker para Ubuntu si aún no están disponibles.

### Topología de red del laboratorio

En VirtualBox, los adaptadores internos deben compartir el nombre
`sanolifood-lab`. No configure puerta de enlace ni DNS en la red interna; cada
VM conserva un primer adaptador NAT o puente únicamente para administración y
descarga de paquetes.

| Sistema | Adaptador de gestión | Adaptador interno | Dirección interna |
|---|---|---|---|
| Ubuntu SOC | `enp0s3`, DHCP | `enp0s8` | `10.20.0.10/24` |
| Windows endpoint | NAT, DHCP | `sanolifood-lab` | `10.20.0.20/24` |
| Kali de validación | NAT temporal | `sanolifood-lab` | `10.20.0.30/24` |

Para que Suricata pueda observar también tráfico lateral, configure el modo
promiscuo del segundo adaptador de Ubuntu como **Permitir todo**. Las pruebas
de esta fase solo se ejecutan contra activos propios del segmento
`10.20.0.0/24`.

Prepare el requisito del indexer y hágalo persistente:

```bash
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-sanolifood.conf
sudo sysctl --system
sysctl vm.max_map_count
```

## Instalación desde cero

### 1. Clonar y revisar la versión

```bash
git clone https://github.com/Jocarsoli2001/sanolifood-soc.git
cd sanolifood-soc
git status -sb
```

Para una evaluación formal debe utilizarse un tag publicado, no una rama de
desarrollo. La base SOAR validada es:

```bash
git checkout v0.7.0
```

### 2. Crear la configuración local de la aplicación

El siguiente bloque genera tres secretos diferentes y conserva únicamente el
archivo local `.env`, que está ignorado por Git:

```bash
make bootstrap

SESSION_SECRET_VALUE="$(openssl rand -hex 32)"
POSTGRES_PASSWORD_VALUE="$(openssl rand -hex 24)"
ADMIN_PASSWORD_VALUE="Sf!$(openssl rand -hex 12)Aa1"

sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=${SESSION_SECRET_VALUE}|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VALUE}|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://sanolifood_app:${POSTGRES_PASSWORD_VALUE}@postgres:5432/sanolifood|" .env
sed -i "s|^BOOTSTRAP_ADMIN_PASSWORD=.*|BOOTSTRAP_ADMIN_PASSWORD=${ADMIN_PASSWORD_VALUE}|" .env

printf 'Usuario inicial: admin.sanolifood\n'
printf 'Contraseña inicial: %s\n' "$ADMIN_PASSWORD_VALUE"
printf 'Guarde la contraseña fuera del repositorio.\n'

unset SESSION_SECRET_VALUE POSTGRES_PASSWORD_VALUE ADMIN_PASSWORD_VALUE
git check-ignore .env
```

El último comando debe devolver `.env`. No continúe si el archivo no está
ignorado. No reutilice estas credenciales en ningún otro sistema.

### 3. Validar los recursos y la configuración

```bash
make config
make wazuh-preflight
make suricata-preflight
make soar-static-check
```

Corrija cualquier resultado `FAIL` antes de iniciar los servicios.

### 4. Levantar el laboratorio completo

```bash
make soc-up
```

En el primer arranque se descargan y construyen varias imágenes; la duración
depende del equipo y de la conexión. El proceso realiza healthchecks y genera
automáticamente las credenciales y certificados locales de Wazuh y del plano
SOAR. n8n comienza en `dry-run` y Wazuh todavía no reenvía alertas.

En el primer despliegue, el editor n8n solo escucha en loopback. Desde el equipo
de administración abra un túnel SSH y mantenga esa consola abierta:

```bash
ssh -L 5678:127.0.0.1:5678 socadmin@IP_DE_UBUNTU
```

Visite `http://127.0.0.1:5678`, cree la cuenta propietaria local de n8n y
después publique los workflows desde Ubuntu:

```bash
make soar-install-workflows
```

El último comando solo habilita el reenvío autenticado de Wazuh si los cinco
workflows se importan, publican y quedan saludables.

### 5. Verificar la instalación

```bash
make soc-health
make test
make wazuh-test-rules
make suricata-test-rules
make soar-validate-live
```

El resultado esperado antes de enrolar los endpoints es:

- PostgreSQL, aplicación, Nginx, Wazuh indexer, manager, dashboard y Suricata en
  estado `healthy`;
- endpoint HTTP `/health/ready` disponible;
- 39 pruebas de aplicación y del plano SOAR superadas;
- reglas de aplicación 110010, 110020 y 110030 aprobadas;
- reglas NDR 110100, 110110, 110120, 110130 y 110140 aprobadas;
- fixtures EDR 110200, 110210, 110211 y 110220 aprobados.
- validación SOAR con evidencia `completed` y contención `simulated`.

### 6. Abrir las interfaces

Obtenga la dirección IPv4 de Ubuntu:

```bash
ip -br -4 addr
```

Desde otro equipo de la red del laboratorio abra:

- SanoliFood Operations: `http://IP_DE_UBUNTU:8080`
- Wazuh Dashboard: `https://IP_DE_UBUNTU:8443`
- n8n SOAR: `http://127.0.0.1:5678` mediante túnel SSH

El dashboard utiliza una CA propia del laboratorio. Compruebe que la dirección
pertenece a su VM antes de aceptar la advertencia del navegador. Consulte las
credenciales localmente y no copie su salida a evidencias:

```bash
make wazuh-credentials
```

El usuario inicial de Wazuh Dashboard es `admin`.

## Despliegue de endpoints

Esta fase registra dos activos reales en el manager y distribuye políticas por
grupos. El agente Ubuntu observa autenticación y cambios en
`/etc/sanolifood`; el agente Windows incorpora FIM, eventos de PowerShell,
OpenSSH y Sysmon. Las contraseñas de enrolamiento permanecen fuera de Git.

### 1. Preparar el manager y el sensor interno

Con Ubuntu y Windows encendidos, ejecute en el repositorio de Ubuntu:

```bash
make endpoint-preflight
make upgrade-0.6
```

El segundo comando fija Suricata en `enp0s8` con `HOME_NET=10.20.0.0/24`,
recrea el manager con las políticas versionadas y crea los grupos
`sanolifood-linux` y `sanolifood-windows`. Los valores quedan persistidos en
`suricata/runtime/.env`, por lo que `make soc-up` no vuelve a seleccionar
silenciosamente `enp0s3`. Los puertos 1514, 1515 y 514 quedan enlazados a
`10.20.0.10`, no a la interfaz de gestión.

### 2. Instalar el agente Ubuntu

```bash
make endpoint-install-ubuntu
sudo systemctl status wazuh-agent --no-pager
```

El instalador usa el repositorio oficial, exige exactamente Wazuh Agent
`4.14.7-1`, conserva la contraseña solo en memoria, activa `rsyslog` y deja el
paquete retenido para evitar una actualización accidental durante la
evaluación.

### 3. Transferir el instalador a Windows

Sustituya `USUARIO_WINDOWS` por la cuenta habilitada en OpenSSH:

```bash
make endpoint-stage-windows \
  WINDOWS_SSH=USUARIO_WINDOWS@10.20.0.20
```

Consulte la contraseña de enrolamiento únicamente en la consola de Ubuntu. No
la guarde en scripts, capturas ni historial:

```bash
make endpoint-registration-password
```

### 4. Instalar el agente Windows y Sysmon

Abra **PowerShell como administrador** dentro de la VM Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "$env:USERPROFILE\SanoliFood-Endpoint\Install-SanoliFoodEndpoint.ps1"
```

Introduzca la contraseña cuando aparezca el prompt seguro. El script descarga
el MSI Wazuh `4.14.7-1` y Sysmon `15.21` desde sus repositorios oficiales,
valida sus firmas Authenticode, registra hashes SHA-256, aplica la configuración
versionada y no escribe la contraseña en el manifiesto.

### 5. Confirmar los dos agentes

Espere hasta 60 segundos y vuelva a Ubuntu:

```bash
make endpoint-health
```

El resultado correcto muestra `sanolifood-ubuntu-01` y
`sanolifood-win-01` en estado `active`, además de ambas políticas centrales.
En el dashboard también deben aparecer los dos activos en **Agents summary**.

## Recorrido funcional de verificación

Los datos de demostración permiten validar la separación de funciones sin
modificar directamente la base de datos.

### 1. Crear identidades operativas

Acceda con `admin.sanolifood` y cree usuarios distintos para los roles
`warehouse`, `production`, `quality` y `auditor`. Use contraseñas únicas y no las
incluya en capturas.

### 2. Registrar inventario

1. Inicie sesión con el usuario de almacén.
2. Abra **Inventario** y revise los ingredientes de demostración.
3. Registre una recepción de 100 kg de concentrado de tomate con referencia
   `PO-DEMO-001`.
4. Confirme el saldo y el movimiento en el libro.

### 3. Ejecutar un lote

1. Inicie sesión con el usuario de producción.
2. Planifique el lote `SF26-SAL-0018`, producto Salsa de tomate, cantidad 1000.
3. Inicie el lote; la receta v1 consume los materiales de forma transaccional.
4. Envíe el lote a Calidad.

### 4. Tomar una decisión de calidad

1. Inicie sesión con el usuario de calidad.
2. Registre pH 4.3 con límites 4.0–4.6.
3. Compruebe el resultado **Conforme** y libere el lote.
4. En otro lote en proceso, registre pH 5.2 para comprobar la retención
   automática por desviación.

### 5. Revisar la trazabilidad

Acceda como auditor y confirme que los eventos contienen actor, resultado,
recurso e identificador de correlación. También pueden consultarse los últimos
eventos desde Ubuntu:

```bash
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select occurred_at,event_type,outcome,actor_username,correlation_id from audit_events order by id desc limit 25;"'
```

## Ingeniería de detección

### Telemetría de aplicación

La aplicación escribe JSON Lines en
`/var/log/sanolifood/sanolifood.jsonl`. El campo `sf_event_type` delimita el
namespace de SanoliFood y evita colisiones con decoders de otros productos.

| Regla Wazuh | Nivel | Caso de uso | MITRE ATT&CK |
|---:|---:|---|---|
| 110010 | 5 | Fallo individual de autenticación | No aplica |
| 110011 | 10 | Cinco fallos desde la misma IP en 120 s | T1110, T1110.001 |
| 110012 | 9 | Cuenta bloqueada | T1110 |
| 110020 | 8 | Ajuste de inventario de alto valor | No aplica |
| 110030 | 8 | Control de calidad fuera de especificación | No aplica |
| 110040 | 12 | Error no controlado de aplicación | No aplica |

Los eventos empresariales no reciben un mapeo MITRE artificial. Solo se asigna
una técnica cuando el comportamiento observado corresponde a una actividad
adversaria.

### Telemetría de red

Suricata captura la interfaz interna versionada para el laboratorio, escribe
`eve.json` y Wazuh enriquece las firmas seleccionadas.

| SID Suricata | Regla Wazuh | Caso de uso | MITRE ATT&CK |
|---:|---:|---|---|
| 9900001 | 110100 | Marcador inocuo de validación extremo a extremo | No aplica |
| 9900002 | 110110 | Posible escaneo TCP de servicios | T1046 |
| 9900003 | 110120 | Enumeración de rutas web sensibles | T1595.002 |
| 9900004 | 110130 | Indicador de inyección SQL en URI | T1190 |
| 9900005 | 110140 | Enumeración HTTP de alta frecuencia | T1595.002 |

### Telemetría de endpoint

Las políticas de los agentes se administran de forma centralizada desde
`wazuh/config/manager/shared`. Ubuntu aporta autenticación, inventario del host
y FIM; Windows complementa FIM con Sysmon, PowerShell y OpenSSH.

| Regla Wazuh | Nivel | Caso de uso | MITRE ATT&CK |
|---:|---:|---|---|
| 110200 | 5 | Marcador inocuo de creación de proceso observado por Sysmon | No aplica |
| 110210 | 8 | Cambio en configuración de calidad del endpoint Ubuntu | T1565.001 |
| 110211 | 8 | Cambio en configuración de calidad del endpoint Windows | T1565.001 |
| 110220 | 5 | Marcador inocuo de recolección de logs Ubuntu | No aplica |

Las reglas 110200 y 110220 validan la ruta de telemetría y no representan un
ataque. Las reglas FIM indican una modificación que debe investigarse; el
contexto del escenario determina si es autorizada o adversaria.

## Validación NDR en vivo

La prueba siguiente usa una cabecera de laboratorio inofensiva; no explota la
aplicación. Debe enviarse desde un equipo distinto de la VM Ubuntu para que el
tráfico atraviese la interfaz observada.

Desde PowerShell, sustituya la IP:

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri "http://IP_DE_UBUNTU:8080/health/ready" `
  -Headers @{"X-SanoliFood-Lab"="ndr-validation"}
```

Espere aproximadamente 20 segundos y ejecute en Ubuntu:

```bash
make suricata-check-live
```

Resultado esperado:

```text
OK   Suricata EVE     signature_id=9900001
OK   Wazuh alert      rule=110100
PASS live NDR telemetry path: network -> Suricata -> EVE -> Wazuh.
```

La regla 110100 confirma la ruta de datos. No debe contabilizarse como ataque en
las métricas del TFM.

## Validación EDR en vivo

Estas pruebas son benignas y solo crean archivos de validación en las rutas
sintéticas del laboratorio. No modifican archivos del sistema ni desactivan
controles de seguridad.

En Ubuntu:

```bash
sudo ./endpoints/scripts/validate-linux.sh
```

En una PowerShell elevada de Windows:

```powershell
& "$env:USERPROFILE\SanoliFood-Endpoint\Test-SanoliFoodEndpoint.ps1"
```

Espere aproximadamente 30 segundos y ejecute en Ubuntu:

```bash
make endpoint-check-live
```

Resultado esperado:

```text
OK   Windows Sysmon probe   rule=110200
OK   Ubuntu quality FIM     rule=110210
OK   Windows quality FIM    rule=110211
OK   Ubuntu log probe       rule=110220
PASS endpoint telemetry path: host -> Wazuh agent -> manager -> alert.
```

En Wazuh Threat Hunting filtre por los identificadores 110200, 110210, 110211
y 110220. Conserve una captura donde se vean regla, agente, marca temporal y
ruta o proceso, sin mostrar credenciales.

## Respuesta SOAR con n8n

Wazuh entrega únicamente las reglas seleccionadas a n8n mediante un integrador
`custom-*`. Cada mensaje se firma con HMAC-SHA256, se acepta durante cinco
minutos y se deduplica usando los campos estables de la alerta. n8n coordina el
recorrido; el estado durable permanece en el controlador y PostgreSQL.

```mermaid
flowchart TD
    A["Alerta Wazuh"] --> B["Firma y triage n8n"]
    B --> C["Incidente durable"]
    C --> D["Evidencia automática"]
    C --> E{"Decisión humana"}
    E -->|Aprobar| F["Control temporal"]
    E -->|Rechazar| G["Cierre documentado"]
    F --> H["TTL o rollback manual"]
```

El catálogo incluye nueve playbooks y puede combinar varias respuestas en el
mismo incidente:

| Respuesta | Ejecución | Salvaguardas |
|---|---|---|
| Conservar evidencia | Automática | Archivo por incidente, hash de configuración |
| Bloquear IP en la aplicación | Tras aprobación | CIDR autorizado, IP protegida, TTL y rollback |
| Bloquear cuenta | Tras aprobación | Usuario validado, identidades protegidas, TTL y rollback |
| Suspender liberación de lotes | Tras aprobación | Objetivo fijo, TTL y rollback |

Las reglas de validación 110100, 110200 y 110220 solo crean evidencia. Nunca
proponen una contención. Las acciones con impacto comienzan en
`pending_approval`; en el modo inicial `dry-run` terminan como `simulated`.

Operación básica:

```bash
make soar-health
make soar-incidents
make soar-show INCIDENT_ID=UUID
make soar-metrics
```

Para aprobar o rechazar un caso, identifique al analista y documente el motivo:

```bash
make soar-approve \
  INCIDENT_ID=UUID \
  ANALYST=soc.analyst \
  REASON='Origen verificado y contención temporal autorizada'

make soar-reject \
  INCIDENT_ID=UUID \
  ANALYST=soc.analyst \
  REASON='Actividad legítima confirmada durante la investigación'
```

Un fallo transitorio conserva el caso y el número de intentos. Puede reintentarse
de forma explícita; una contención aplicada también puede revertirse antes del
TTL:

```bash
make soar-retry ACTION_ID=UUID ANALYST=soc.analyst
make soar-rollback ACTION_ID=UUID ANALYST=soc.analyst
```

Solo después de superar la validación en seco puede habilitarse el modo real:

```bash
make soar-validate-live
make soar-enable-live CONFIRM=live
make soar-validate-live
```

La segunda prueba aplica y revierte su propio control. `make soar-disable-live`
devuelve la plataforma a simulación. La guía completa se encuentra en
[`n8n/README.md`](n8n/README.md).

## Campaña final de evaluación

El catálogo `evaluation/config/scenarios.json` define ocho recorridos. Cada
ejecución crea un identificador `SF-EVAL-SCN-*` y exige encontrarlo en una
alerta nueva; después relaciona el incidente n8n por `source_alert_id`. Por
ello, una alerta histórica con la misma regla no puede aprobar una prueba.

Kali participa solo en SCN-001 a SCN-004 como cliente HTTP fijo
`10.20.0.30 -> 10.20.0.10:8080`. El ejecutor no acepta otros destinos, aplica
un presupuesto de solicitudes y usa únicamente estímulos deterministas del
laboratorio. SCN-005 y SCN-006 se originan en la aplicación; SCN-007 y SCN-008
se originan en los endpoints Ubuntu y Windows.

Las métricas entre máquinas requieren una fuente horaria común. Ubuntu sirve
NTP mediante Chrony en `10.20.0.10`; Kali y Windows usan esa dirección como
fuente. El preflight exige Chrony sincronizado, comprueba la fuente de Windows
y rechaza diferencias superiores a un segundo. Los intervalos negativos se
marcan como inválidos y no se agregan como ceros.

```bash
make upgrade-0.8
make eval-list
make eval-preflight \
  KALI_SSH=usuario@10.20.0.30 \
  WINDOWS_SSH=usuario@10.20.0.20
make eval-run SCENARIO=SCN-001 KALI_SSH=usuario@10.20.0.30
```

Las ejecuciones que requieren juicio terminan primero en
`PASS_PENDING_DECISION`. La decisión se registra con el `RUN_ID` exacto:

```bash
make eval-decide \
  RUN_ID=SF-EVAL-SCN-... \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Decisión documentada para la ejecución controlada'
```

La campaña comienza en `dry-run`. Si se autoriza una ejecución supervisada en
modo real, `CONFIRM=live` es obligatorio y el orquestador revierte
inmediatamente cada acción reversible aplicada. La guía y la matriz completa
están en [`evaluation/README.md`](evaluation/README.md).

## Evidencias y validación

Las evidencias textuales reproducibles pueden mantenerse en Git después de una
revisión manual. Las capturas, grabaciones y archivos voluminosos deben
conservarse en el archivo externo de anexos.

### Evidencia de negocio: BUS-001

```bash
make evidence-business
```

Capturas recomendadas:

1. dashboard con indicadores empresariales;
2. libro de movimientos de inventario;
3. recetas y lotes de producción;
4. desviación y retención de calidad;
5. auditoría con eventos de negocio.

### Evidencia Wazuh: WAZ-001

Genere primero al menos un evento empresarial y un fallo de acceso, luego:

```bash
make evidence-wazuh
```

Capturas recomendadas:

1. salida completa de `make soc-health`;
2. vista general del dashboard sin credenciales visibles;
3. estado de los procesos del manager;
4. salida de `make wazuh-test-rules`;
5. alerta real con regla, actor, IP e identificador de correlación.

### Evidencia de red: NDR-001

Después de la validación en vivo:

```bash
make evidence-ndr
```

Capturas recomendadas:

1. salida de `make suricata-health`;
2. salida de `make suricata-test-rules`;
3. alerta EVE con SID 9900001;
4. regla Wazuh 110100 en Threat Hunting;
5. salida completa de `make soc-health`;
6. salida de `docker stats --no-stream`.

### Evidencia de endpoints: END-001

Después de completar las dos validaciones EDR:

```bash
make endpoint-health
make endpoint-check-live
make evidence-endpoint WINDOWS_SSH=USUARIO_WINDOWS@10.20.0.20
```

Capturas recomendadas:

1. `make endpoint-health` con ambos agentes activos;
2. resumen de agentes en Wazuh;
3. servicio Wazuh Agent y Sysmon en Windows;
4. evento de creación de proceso en Sysmon Event Viewer;
5. alerta 110200 en Wazuh;
6. alertas FIM 110210 y 110211, una por sistema operativo;
7. inventario del endpoint Windows o Ubuntu en Wazuh;
8. salida completa de `make endpoint-check-live`.

`WINDOWS_SSH` permite incorporar el manifiesto, los servicios y el resultado de
validación de Windows sin copiar credenciales. Si se omite, la evidencia del
manager se genera igualmente. `evidence/END-001` contiene únicamente estado,
versiones, hashes y alertas revisables. Las capturas se conservan en el archivo
externo de anexos.

### Evidencia SOAR: SOAR-001

Después de publicar los workflows y completar la validación:

```bash
make soar-health
make soar-validate-live
make evidence-soar
```

Capturas recomendadas:

1. los cinco workflows publicados en n8n;
2. un incidente con regla, prioridad, playbook y acciones;
3. decisión aprobada con identidad y justificación del analista;
4. contención `simulated` en modo seco;
5. contención `applied` y `rolled_back` en la validación real;
6. salida completa de `make soar-health`;
7. métricas de MTTD, MTTA y comienzo de respuesta;
8. error workflow y auditoría sin credenciales visibles.

`evidence/SOAR-001` conserva estado, versión, casos normalizados, auditoría,
errores, métricas y hashes. No exporta secretos, cookies ni el contenido de las
bases de datos.

### Evidencia de evaluación: EVAL-001

Después de completar los ocho escenarios y sus decisiones:

```bash
make eval-summary
make evidence-evaluation
```

`EVAL-001` conserva el catálogo, resultados CSV/JSON, métricas agregadas,
alertas nuevas, incidentes relacionados, estados de contenedores y hashes. No
incorpora las credenciales locales, secretos SOAR ni volcados de bases de datos.

Antes de `git add`, revise siempre:

```bash
git status --short
git diff --check
git check-ignore .env wazuh/runtime/.env suricata/runtime/.env n8n/runtime/.env
```

Nunca publique `.env`, contraseñas, cookies, claves privadas, certificados
privados, capturas con credenciales ni volcados completos de paquetes.

## Operación diaria

### Estado y logs

```bash
make soc-health
make ps
make wazuh-ps
make suricata-ps
make endpoint-health
make soar-ps

make logs
make wazuh-logs
make suricata-logs
make soar-logs
```

Los objetivos `*-logs` permanecen en primer plano; salga con `Ctrl+C`.

### Apagado y arranque

El apagado siguiente conserva todos los volúmenes:

```bash
make suricata-down
make soar-down
make wazuh-down
make down
```

Después de reiniciar Ubuntu:

```bash
cd ~/sanolifood-soc
make soc-up
make soc-health
make endpoint-health
```

El agente Ubuntu arranca mediante `systemd`; el agente Windows y Sysmon
arrancan como servicios automáticos cuando se enciende su VM.

Antes de cambios de versión o de configuración SOAR, cree un respaldo local:

```bash
make soar-backup
```

El respaldo contiene secretos y queda excluido de Git. Consérvelo en una
ubicación protegida distinta del repositorio.

### Cambios en reglas

```bash
make wazuh-reload-rules
make wazuh-test-rules
make suricata-config-test
make suricata-test-rules
```

### Reconstrucción de la aplicación

```bash
make rebuild
```

Este objetivo conserva PostgreSQL. Para evitar que Nginx mantenga una dirección
de contenedor antigua, la reconstrucción vuelve a levantar el stack principal
completo.

### Reinicio destructivo del estado empresarial

```bash
make reset-lab
```

Este comando elimina únicamente los contenedores, redes y volúmenes declarados
por el stack principal de SanoliFood, genera secretos nuevos, reconstruye la
aplicación y ejecuta las pruebas. **Destruye los usuarios y datos empresariales
de PostgreSQL.** No elimina los volúmenes de Wazuh, Suricata o SOAR. Por
seguridad se negará a continuar mientras el controlador SOAR esté desplegado;
ejecute antes `make soar-down` y, después de la reconstrucción, vuelva a iniciar
y publicar el plano con `make soar-up` y `make soar-install-workflows`.

No utilice `docker compose down -v` ni `docker volume prune` como parte del flujo
operativo normal.

## Resolución de problemas

### La aplicación no alcanza `healthy`

```bash
docker compose ps
docker compose logs --no-color --tail=150 app
docker compose exec -T app alembic current
docker compose exec -T app python -m sanolifood.schema_guard
```

Si se modificaron plantillas, estáticos o dependencias, use `make rebuild` en
lugar de recrear únicamente el contenedor de la aplicación.

### Wazuh no inicia

```bash
sysctl vm.max_map_count
free -h
df -h /
make wazuh-preflight
make wazuh-ps
make wazuh-logs
```

No elimine `wazuh/runtime/certs` parcialmente. Si la generación de certificados
se interrumpe, preserve el directorio para diagnóstico y muévalo completo antes
de volver a ejecutar `make wazuh-up`.

### Suricata detecta una interfaz incorrecta

Compruebe las interfaces y el runtime persistido:

```bash
ip -br link
grep -E 'SURICATA_INTERFACE|SURICATA_HOME_NET' suricata/runtime/.env
```

Puede forzar valores solo para el descubrimiento:

```bash
SURICATA_INTERFACE_OVERRIDE=enp0s8 \
SURICATA_HOME_NET_OVERRIDE=10.20.0.0/24 \
make suricata-discover

make suricata-up
```

Adapte interfaz e IP a su laboratorio. Los valores se guardan en
`suricata/runtime/.env` y no se versionan.

### Un endpoint aparece desconectado

En Ubuntu compruebe servicios, puertos y agentes:

```bash
sudo systemctl status wazuh-agent --no-pager
make endpoint-preflight
make endpoint-health
```

En Windows, desde PowerShell elevada:

```powershell
Get-Service WazuhSvc,Sysmon64 -ErrorAction SilentlyContinue
Test-NetConnection 10.20.0.10 -Port 1514
Test-NetConnection 10.20.0.10 -Port 1515
Get-Content "${env:ProgramFiles(x86)}\ossec-agent\ossec.log" -Tail 80
```

No elimine `client.keys` para “probar de nuevo” sin conservar antes el estado y
el diagnóstico. Un reenrolamiento crea una identidad nueva y debe documentarse.

### Las políticas centralizadas no aparecen

```bash
make endpoint-configure
make wazuh-reload-rules
make endpoint-test-rules
```

Confirme en el dashboard que cada agente pertenece a su grupo. La sincronización
puede tardar algunos segundos después del primer enrolamiento.

### La regla 110100 no aparece

- Envíe la petición desde otro equipo o VM, no desde el propio host Ubuntu.
- Confirme que la solicitud llega a `http://IP_DE_UBUNTU:8080`.
- Ejecute `make suricata-health` y `make wazuh-health`.
- Revise `make suricata-logs` y espere al menos 20 segundos antes de ejecutar
  `make suricata-check-live`.

### Las credenciales de Wazuh no están disponibles

```bash
make wazuh-up
make wazuh-credentials
```

Las credenciales se generan en el primer arranque y permanecen en
`wazuh/runtime/.env`, con permisos restrictivos y fuera de Git.

### n8n está healthy pero Wazuh no crea incidentes

```bash
make soar-health
make soar-static-check
cat n8n/runtime/integration.state
make soar-install-workflows
make wazuh-logs
```

El estado debe ser `enabled`. Si es `disabled`, no edite `ossec.conf`
manualmente: vuelva a publicar los workflows. Una petición sin firma al webhook
debe ser rechazada; ese rechazo confirma que el endpoint existe y que la
autenticación funciona.

### Una acción SOAR queda en `failed`

```bash
make soar-show INCIDENT_ID=UUID
make soar-logs
make soar-retry ACTION_ID=UUID ANALYST=soc.analyst
```

Revise primero el error persistido. El reintento mantiene el mismo `action_id` y
está limitado a cinco intentos. No cree manualmente un segundo bloqueo para el
mismo incidente.

### Se necesita detener n8n de inmediato

```bash
make soar-disable-integration
make soar-disable-live
make soar-down
```

Los incidentes y volúmenes se conservan. Los controles ya aplicados siguen
teniendo su vencimiento en la aplicación; si n8n permanecerá apagado más allá
del TTL, reviértalos antes de detener el controlador.

## Reproducibilidad

Una reproducción se considera válida cuando un tercero puede, desde un clon
limpio y sin copiar volúmenes del autor:

1. generar su propia configuración local;
2. levantar el laboratorio con `make soc-up`;
3. obtener todos los healthchecks en verde;
4. superar las pruebas de aplicación y reglas;
5. completar el recorrido empresarial;
6. generar la alerta NDR 110100 desde un segundo equipo;
7. enrolar Ubuntu y Windows desde las fuentes versionadas;
8. obtener las alertas EDR 110200, 110210, 110211 y 110220;
9. publicar los cinco workflows y superar la validación SOAR en `dry-run`;
10. aplicar y revertir la contención controlada en modo real;
11. ejecutar SCN-001 a SCN-008 con marcadores únicos y decisiones registradas;
12. producir nuevas evidencias BUS-001, WAZ-001, NDR-001, END-001, SOAR-001 y
    EVAL-001.

Para la entrega final se recomienda repetir este procedimiento en una VM nueva
y registrar tiempo de despliegue, incidencias y consumo de recursos.

## Decisiones de arquitectura

Las decisiones estables se documentan como ADR en [`docs/adr`](docs/adr):

- monolito modular para la aplicación empresarial;
- sesiones firmadas y control de acceso por roles;
- transacciones y telemetría de negocio;
- Wazuh single-node mediante Compose;
- namespace propio para eventos de aplicación;
- sensor Suricata en la interfaz interna del host;
- telemetría de endpoint con políticas Wazuh centralizadas y Sysmon;
- plano SOAR durable con aprobación, TTL, idempotencia y rollback.
- campaña atribuible con objetivo fijo, presupuestos y resultados aislados.

## Limitaciones del hito v0.8.0

- La aplicación se publica por HTTP porque el entorno es un laboratorio aislado;
  no es una configuración apta para Internet.
- El certificado del dashboard es autofirmado por la CA local del laboratorio.
- Suricata observa la interfaz interna de Ubuntu y no pretende sustituir una
  arquitectura física con TAP o SPAN.
- Sysmon está configurado para un laboratorio acotado; una organización real
  necesitaría tuning, retención y gestión de cambios adicionales.
- Las contenciones se limitan deliberadamente a la aplicación empresarial; no
  modifican firewalls del host ni ejecutan comandos remotos sobre endpoints.
- La cuenta propietaria inicial de n8n se crea manualmente para no versionar ni
  automatizar una credencial administrativa.
- Las firmas locales están diseñadas para pruebas deterministas; un despliegue
  productivo requeriría gestión adicional de reglas, tuning y reducción de
  falsos positivos.

## Hoja de ruta

1. ejecutar y repetir los ocho escenarios desde el entorno limpio;
2. analizar MTTD, tiempos de triage, decisión, respuesta y rollback;
3. documentar los controles negativos y la cobertura MITRE ATT&CK;
4. cerrar la memoria, anexos técnicos y demostración de cinco minutos.

## Referencias técnicas

- [Docker Engine para Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [PostgreSQL 17](https://www.postgresql.org/docs/17/)
- [Wazuh Documentation](https://documentation.wazuh.com/current/)
- [Instalación de Wazuh Agent en Linux](https://documentation.wazuh.com/current/installation-guide/wazuh-agent/wazuh-agent-package-linux.html)
- [Instalación de Wazuh Agent en Windows](https://documentation.wazuh.com/current/installation-guide/wazuh-agent/wazuh-agent-package-windows.html)
- [Configuración centralizada de agentes Wazuh](https://documentation.wazuh.com/current/user-manual/reference/centralized-configuration.html)
- [Suricata 8.0.6 Documentation](https://docs.suricata.io/en/suricata-8.0.6/)
- [Microsoft Sysmon](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon)
- [n8n self-hosting](https://docs.n8n.io/hosting/)
- [Wazuh: integración con APIs externas](https://documentation.wazuh.com/current/user-manual/manager/integration-with-external-apis.html)
- [MITRE ATT&CK Enterprise](https://attack.mitre.org/techniques/enterprise/)

La evolución técnica del repositorio se resume en
[`CHANGELOG.md`](CHANGELOG.md).
