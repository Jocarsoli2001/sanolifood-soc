# Historial de cambios

Este archivo resume los hitos funcionales de SanoliFood SOC. Las notas de
instalación y validación vigentes se mantienen únicamente en el `README.md`.

## En desarrollo

- Escenarios controlados y métricas de detección.
- Respuesta semiautomatizada con n8n y aprobación humana.

## 0.6.0 — 2026-08-22

### Añadido

- Agentes Wazuh 4.14.7 reproducibles para Ubuntu y Windows.
- Grupos `sanolifood-linux` y `sanolifood-windows` con configuración
  centralizada, etiquetas de activo, FIM y recolección de eventos.
- Sysmon 15.21 con perfil acotado para procesos, conexiones internas, archivos
  empresariales y ubicaciones de persistencia.
- Instaladores firmados/verificados, staging por OpenSSH y hashes de componentes
  registrados sin almacenar la contraseña de enrolamiento.
- Reglas 110200, 110210, 110211 y 110220 para pruebas EDR, FIM y logcollector.
- Healthcheck de agentes, validación en vivo y evidencia END-001 automatizada.
- Persistencia de la interfaz Suricata seleccionada entre reinicios del stack.

### Seguridad y reproducibilidad

- La contraseña de enrolamiento solo se consulta localmente y no se incorpora a
  scripts, manifiestos ni evidencias.
- Las pruebas de endpoint son benignas y operan sobre rutas sintéticas del
  laboratorio.
- El README público documenta la topología `10.20.0.0/24`, instalación,
  validación, diagnóstico y evidencias.

## 0.5.1 — 2026-08-21

### Documentación

- Consolidación de la guía pública en el README principal.
- Eliminación de instrucciones internas fragmentadas y artefactos temporales.
- Conservación de ADR, evidencia técnica y scripts necesarios para reproducir
  el laboratorio.

## 0.5.0 — 2026-08-21

### Añadido

- Sensor Suricata 8.0.6 en modo IDS sobre la interfaz de borde de Ubuntu.
- Persistencia de telemetría EVE JSON e ingestión de solo lectura por Wazuh.
- Cinco firmas locales deterministas en el rango 9900001–9900005.
- Reglas Wazuh 110100–110140 con contexto y mapeo MITRE ATT&CK.
- Preflight, descubrimiento de red, healthchecks, pruebas y recolección de
  evidencia NDR automatizados.

### Validado

- Ruta en vivo `red -> Suricata -> EVE -> Wazuh` mediante SID 9900001 y regla
  Wazuh 110100.
- Configuración de Suricata y ocho fixtures de detección aprobados.
- Stack completo saludable con aplicación, Wazuh y Suricata.

## 0.4.0 — 2026-08-19

### Añadido

- Wazuh 4.14.7 single-node con manager, indexer y dashboard mediante Compose.
- Certificados y credenciales locales generados en runtime y excluidos de Git.
- Ingestión de telemetría JSONL de SanoliFood.
- Reglas 110010–110040 para autenticación, anomalías de negocio y errores.
- Correlación de cinco fallos de autenticación con MITRE T1110/T1110.001.
- Pruebas automatizadas de reglas y evidencia WAZ-001.

### Validado

- Servicios Wazuh saludables y dashboard disponible mediante HTTPS.
- Detección real de fallo de acceso y correlación de fuerza bruta.
- 28 pruebas aisladas de aplicación superadas.

## 0.3.0 — 2026-08-17

### Añadido

- Núcleo empresarial para inventario, recetas, producción y calidad.
- Migración Alembic `20260817_0003`.
- Transacciones para consumo de materiales y prevención de saldos negativos.
- Retención automática de lotes fuera de especificación.
- Eventos empresariales correlacionados y evidencia BUS-001.

## 0.2.2 — 2026-08-17

### Corregido

- Aislamiento de pruebas mediante SQLite en memoria.
- Verificación del esquema PostgreSQL después de ejecutar pytest.
- Reconstrucción integral para evitar referencias obsoletas del proxy inverso.

## 0.2.1 — 2026-08-17

### Añadido

- Identidad corporativa, sesiones firmadas y contraseñas con Argon2.
- Control de acceso por roles, bloqueo temporal y auditoría.
- Portal de acceso y vistas administrativas.

## 0.1.0 — 2026-08-13

### Añadido

- Base de FastAPI, PostgreSQL y Nginx segmentada con Docker Compose.
- Migraciones Alembic, healthchecks y telemetría JSON estructurada.
- Contenedores con usuario no privilegiado, filesystem de solo lectura y
  opciones de endurecimiento iniciales.
