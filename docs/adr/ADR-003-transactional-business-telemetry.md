# ADR-003 — Dominio empresarial transaccional como fuente de telemetría

- Estado: aceptada
- Fecha: 2026-08-17

## Contexto

El laboratorio SOC necesita una aplicación suficientemente realista para que los
ataques, errores de autorización y anomalías de negocio produzcan señales útiles.
Pantallas estáticas o datos simulados únicamente en la interfaz no permitirían
demostrar detección, correlación ni respuesta con rigor.

## Decisión

Inventario, producción y calidad se implementan dentro del monolito modular
existente y comparten una única transacción PostgreSQL por operación. Los lotes
referencian una versión inmutable de receta. Al iniciarse un lote se bloquean las
filas de ingredientes, se calculan los consumos proporcionales y se rechaza toda la
operación si cualquier saldo sería negativo.

Los cambios relevantes generan dos evidencias complementarias:

1. entidades de negocio normalizadas para reconstruir el estado;
2. eventos de auditoría y logs JSON para Wazuh y los playbooks n8n.

## Consecuencias

- Es posible reconstruir quién modificó qué recurso, cuándo y desde qué origen.
- Las desviaciones de calidad y ajustes de inventario son casos de uso SOC reales.
- La transacción evita lotes iniciados con consumos parciales.
- El despliegue sigue siendo reproducible con un único Compose.
- La integración Wazuh/Suricata/n8n puede evolucionar sin cambiar el modelo de
  negocio ni fabricar telemetría artificial.
