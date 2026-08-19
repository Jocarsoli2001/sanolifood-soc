# ADR-005 — Namespace del tipo de evento en telemetría SanoliFood

## Estado

Aceptado para v0.4.0.

## Contexto

SanoliFood utiliza internamente `event_type` en su modelo transaccional de
auditoría. La regla oficial 86600 de Wazuh 4.14.7 inicia el árbol de reglas de
Suricata cuando un documento JSON contiene simultáneamente `timestamp` y
`event_type`. Por ello, un evento legítimo de la aplicación podía decodificarse
correctamente pero quedar etiquetado como `ids,suricata` antes de alcanzar las
reglas locales.

## Decisión

El contrato JSON enviado al SIEM expone el tipo como `sf_event_type`. La
aplicación conserva `event_type` en código y PostgreSQL; el cambio se realiza
exclusivamente en el formateador de logging. Las reglas 110000–110040 consumen
el campo namespaced.

## Consecuencias

- Los eventos empresariales no heredan grupos ni métricas de Suricata.
- La futura ingesta EVE de Suricata puede usar las reglas oficiales sin
  exclusiones ni modificaciones.
- El esquema de auditoría y las migraciones de negocio no cambian.
- Las pruebas del formateador verifican que `event_type` no se filtra al
  contrato de transporte.
