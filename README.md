# SanoliFood SOC

Laboratorio SOC reproducible para una empresa ficticia de procesamiento de
alimentos. El proyecto integra una aplicación empresarial trazable,
monitorización SIEM, telemetría de red IDS/NDR y reglas de detección
versionadas en un entorno desplegable con Docker Compose.

> Uso autorizado: este repositorio está diseñado exclusivamente para un
> laboratorio propio, aislado y controlado. No ejecute las validaciones de
> seguridad contra sistemas o redes de terceros.

## Estado del proyecto

El hito técnico documentado es **SanoliFood SOC v0.5.0**. La aplicación conserva
la versión **0.4.0** porque el incremento v0.5.0 añade el sensor de red sin
modificar su código de negocio.

| Capacidad | Estado | Validación reproducible |
|---|---|---|
| Aplicación SanoliFood Operations | Operativa | Healthchecks, migraciones y 28 pruebas |
| Identidad, sesiones, RBAC y auditoría | Operativa | Cinco roles y eventos correlacionados |
| Inventario, producción y calidad | Operativa | Recorrido empresarial de extremo a extremo |
| Wazuh manager, indexer y dashboard | Operativo | Healthchecks y reglas probadas con `wazuh-logtest` |
| Suricata IDS/NDR | Operativo | EVE JSON, reglas locales y alerta real en Wazuh |
| Agentes Wazuh en endpoints | Pendiente | Próximo incremento |
| Automatización semiautomatizada con n8n | Pendiente | Próximo incremento |
| Campaña completa de escenarios y métricas | Pendiente | Fase de validación final |

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
7. incorporación posterior de respuesta semiautomatizada y métricas.

El caso de estudio representa a **SanoliFood SA**, una organización ficticia
que administra ingredientes, recetas, lotes de producción, controles de calidad
y decisiones de liberación. Todos los datos incluidos son sintéticos; el
proyecto no depende de datos personales ni de información empresarial real.

## Arquitectura

```mermaid
flowchart TD
    C["Equipo externo<br/>Windows o Kali"] -->|HTTP 8080| N["Nginx<br/>zona DMZ"]
    C -->|Tráfico observado| S["Suricata IDS/NDR<br/>interfaz del host"]
    N --> A["FastAPI<br/>SanoliFood Operations"]
    A --> P["PostgreSQL<br/>datos transaccionales"]
    A -->|JSONL| W["Wazuh manager"]
    S -->|EVE JSON| W
    W --> I["Wazuh indexer"]
    I --> D["Wazuh dashboard<br/>HTTPS 8443"]
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
| Suricata | 8.0.6 | IDS/NDR y generación de EVE JSON |

### Puertos publicados

| Puerto | Protocolo | Servicio | Exposición prevista |
|---:|---|---|---|
| 8080 | TCP/HTTP | SanoliFood Operations mediante Nginx | Red del laboratorio |
| 8443 | TCP/HTTPS | Wazuh Dashboard | Red del laboratorio |
| 1514 | TCP | Eventos de agentes Wazuh | Endpoints futuros |
| 1515 | TCP | Enrolamiento de agentes Wazuh | Endpoints futuros |
| 514 | UDP | Entrada syslog reservada | Fuentes futuras |

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
├── evidence/            Evidencia textual revisada y no secreta
├── docs/adr/             Decisiones de arquitectura
├── detections/          Espacio para casos de detección adicionales
├── evaluation/          Métricas y resultados del TFM
├── n8n/                 Flujos de respuesta futuros
├── scenarios/           Escenarios controlados futuros
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
- Conectividad entre la VM Ubuntu y un segundo equipo o VM de validación.

Los preflight checks de Wazuh exigen 4 CPU, 8 GiB de RAM, 50 GiB libres y
`vm.max_map_count >= 262144`. Suricata requiere un host Linux porque utiliza el
namespace de red del host y capacidades de captura de paquetes.

### Software del host

```bash
sudo apt update
sudo apt install -y git make curl openssl iproute2 ca-certificates
docker --version
docker compose version
git --version
```

Docker Engine y el complemento Docker Compose deben estar instalados y el
usuario del laboratorio debe poder ejecutar `docker` sin `sudo`. Siga la
documentación oficial de Docker para Ubuntu si aún no están disponibles.

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
desarrollo. Cuando el tag v0.5.0 esté disponible:

```bash
git checkout v0.5.0
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
```

Corrija cualquier resultado `FAIL` antes de iniciar los servicios.

### 4. Levantar el laboratorio completo

```bash
make soc-up
```

En el primer arranque se descargan y construyen varias imágenes; la duración
depende del equipo y de la conexión. El proceso realiza healthchecks y genera
automáticamente las credenciales y certificados locales de Wazuh.

### 5. Verificar la instalación

```bash
make soc-health
make test
make wazuh-test-rules
make suricata-test-rules
```

El resultado esperado del hito v0.5.0 es:

- PostgreSQL, aplicación, Nginx, Wazuh indexer, manager, dashboard y Suricata en
  estado `healthy`;
- endpoint HTTP `/health/ready` disponible;
- 28 pruebas de aplicación superadas;
- reglas de aplicación 110010, 110020 y 110030 aprobadas;
- reglas NDR 110100, 110110, 110120, 110130 y 110140 aprobadas.

### 6. Abrir las interfaces

Obtenga la dirección IPv4 de Ubuntu:

```bash
ip -br -4 addr
```

Desde otro equipo de la red del laboratorio abra:

- SanoliFood Operations: `http://IP_DE_UBUNTU:8080`
- Wazuh Dashboard: `https://IP_DE_UBUNTU:8443`

El dashboard utiliza una CA propia del laboratorio. Compruebe que la dirección
pertenece a su VM antes de aceptar la advertencia del navegador. Consulte las
credenciales localmente y no copie su salida a evidencias:

```bash
make wazuh-credentials
```

El usuario inicial de Wazuh Dashboard es `admin`.

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

Suricata captura la interfaz de la ruta predeterminada de Ubuntu, escribe
`eve.json` y Wazuh enriquece las firmas seleccionadas.

| SID Suricata | Regla Wazuh | Caso de uso | MITRE ATT&CK |
|---:|---:|---|---|
| 9900001 | 110100 | Marcador inocuo de validación extremo a extremo | No aplica |
| 9900002 | 110110 | Posible escaneo TCP de servicios | T1046 |
| 9900003 | 110120 | Enumeración de rutas web sensibles | T1595.002 |
| 9900004 | 110130 | Indicador de inyección SQL en URI | T1190 |
| 9900005 | 110140 | Enumeración HTTP de alta frecuencia | T1595.002 |

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

Antes de `git add`, revise siempre:

```bash
git status --short
git diff --check
git check-ignore .env wazuh/runtime/.env suricata/runtime/.env
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

make logs
make wazuh-logs
make suricata-logs
```

Los objetivos `*-logs` permanecen en primer plano; salga con `Ctrl+C`.

### Apagado y arranque

El apagado siguiente conserva todos los volúmenes:

```bash
make suricata-down
make wazuh-down
make down
```

Después de reiniciar Ubuntu:

```bash
cd ~/sanolifood-soc
make soc-up
make soc-health
```

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
de PostgreSQL.** No elimina los volúmenes de Wazuh o Suricata.

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

Compruebe la ruta predeterminada:

```bash
ip route show default
ip -br link
```

Puede forzar valores solo para el descubrimiento:

```bash
SURICATA_INTERFACE_OVERRIDE=enp0s3 \
SURICATA_HOME_NET_OVERRIDE=192.168.56.20/32 \
make suricata-discover

make suricata-up
```

Adapte interfaz e IP a su laboratorio. Los valores se guardan en
`suricata/runtime/.env` y no se versionan.

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

## Reproducibilidad

Una reproducción se considera válida cuando un tercero puede, desde un clon
limpio y sin copiar volúmenes del autor:

1. generar su propia configuración local;
2. levantar el laboratorio con `make soc-up`;
3. obtener todos los healthchecks en verde;
4. superar las pruebas de aplicación y reglas;
5. completar el recorrido empresarial;
6. generar la alerta NDR 110100 desde un segundo equipo;
7. producir nuevas evidencias BUS-001, WAZ-001 y NDR-001.

Para la entrega final se recomienda repetir este procedimiento en una VM nueva
y registrar tiempo de despliegue, incidencias y consumo de recursos.

## Decisiones de arquitectura

Las decisiones estables se documentan como ADR en [`docs/adr`](docs/adr):

- monolito modular para la aplicación empresarial;
- sesiones firmadas y control de acceso por roles;
- transacciones y telemetría de negocio;
- Wazuh single-node mediante Compose;
- namespace propio para eventos de aplicación;
- sensor Suricata en la interfaz de borde del host.

## Limitaciones del hito v0.5.0

- La aplicación se publica por HTTP porque el entorno es un laboratorio aislado;
  no es una configuración apta para Internet.
- El certificado del dashboard es autofirmado por la CA local del laboratorio.
- Suricata observa por defecto la interfaz de borde y no pretende sustituir una
  arquitectura física con TAP o SPAN.
- Wazuh todavía no tiene agentes de endpoint incorporados al despliegue público.
- n8n, los playbooks de contención y la aprobación humana se incorporarán en un
  incremento posterior.
- Las firmas locales están diseñadas para pruebas deterministas; un despliegue
  productivo requeriría gestión adicional de reglas, tuning y reducción de
  falsos positivos.

## Hoja de ruta

1. agente Wazuh en Ubuntu y endpoint Windows, incluyendo FIM y telemetría de
   autenticación;
2. escenarios controlados desde Kali y mapeo formal a MITRE ATT&CK;
3. flujos n8n con aprobación humana y acciones de contención reversibles;
4. medición de MTTD, tasa de detección, falsos positivos, cobertura ATT&CK y
   reproducibilidad;
5. documentación final, anexos técnicos y demostración de cinco minutos.

## Referencias técnicas

- [Docker Engine para Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [PostgreSQL 17](https://www.postgresql.org/docs/17/)
- [Wazuh Documentation](https://documentation.wazuh.com/current/)
- [Suricata 8.0.6 Documentation](https://docs.suricata.io/en/suricata-8.0.6/)
- [MITRE ATT&CK Enterprise](https://attack.mitre.org/techniques/enterprise/)

La evolución técnica del repositorio se resume en
[`CHANGELOG.md`](CHANGELOG.md).
