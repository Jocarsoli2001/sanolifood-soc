# SanoliFood SOC v0.4.0 — Wazuh central e ingesta de telemetría

Este incremento conserva PostgreSQL y el núcleo empresarial v0.3.0. Añade un
stack Wazuh single-node reproducible compuesto por manager, indexer y dashboard,
todos fijados en la versión 4.14.7.

## Resultado técnico

- Wazuh central desplegado con Docker Compose y volúmenes persistentes.
- Certificados autofirmados generados con `wazuh-certs-generator:0.0.4`.
- Credenciales aleatorias y hashes bcrypt almacenados únicamente en
  `wazuh/runtime`, directorio excluido de Git.
- Dashboard HTTPS publicado en el puerto 8443.
- Puertos 1514/TCP, 1515/TCP y 514/UDP disponibles para endpoints y Suricata.
- API y Wazuh indexer sin exposición directa al host.
- Eventos JSON de SanoliFood escritos en el volumen `sanolifood_app_logs` y
  leídos directamente por el manager.
- Campo de transporte `sf_event_type` aislado del esquema EVE/Suricata para
  impedir clasificaciones cruzadas; el modelo de auditoría conserva
  `event_type`.
- Reglas locales 110000–110040 para autenticación, inventario, calidad y errores.
- Pruebas automatizadas con `wazuh-logtest` y recolección `WAZ-001`.

## Instalación sobre v0.3.0

Las instrucciones de transferencia desde Windows y superposición segura están
en `docs/IMPLEMENTATION-04-wazuh-central.md`. Después de aplicarlo sobre
`~/sanolifood-soc`:

```bash
cd ~/sanolifood-soc
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh wazuh/scripts/*.sh
make wazuh-preflight
make upgrade-0.4
```

`make upgrade-0.4` crea un nuevo respaldo PostgreSQL, actualiza únicamente la
imagen de la aplicación, conserva los volúmenes, genera certificados y levanta
Wazuh. No ejecuta `down -v`.

## Validación

```bash
make soc-health
make wazuh-test-rules
make test
```

Resultados esperados:

```text
OK   postgres
OK   app
OK   nginx
OK   wazuh.indexer
OK   wazuh.manager
OK   wazuh.dashboard
OK   auth-login-failed.json       rule=110010
OK   inventory-adjustment.json    rule=110020
OK   quality-check-failed.json    rule=110030
28 passed
```

Consulta las instrucciones completas y el tratamiento de evidencia en
`docs/IMPLEMENTATION-04-wazuh-central.md`.
