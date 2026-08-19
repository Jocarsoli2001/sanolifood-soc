# ADR-004: Wazuh single-node desacoplado mediante Compose

- Estado: aceptado
- Fecha: 2026-08-19

## Contexto

El TFM exige un laboratorio SOC reproducible y el profesor requiere que la
infraestructura central se despliegue con Docker Compose. El equipo disponible
tiene 4 CPU virtuales y aproximadamente 9.5 GiB de RAM, por lo que un clúster
Wazuh multinodo no es adecuado para esta fase.

## Decisión

Desplegar manager, indexer y dashboard Wazuh 4.14.7 en un Compose independiente
de la aplicación. Compartir únicamente una red SOC y el volumen de telemetría
necesario. Mantener API e indexer sin puertos publicados y exponer solo HTTPS,
registro de agentes y syslog.

Los certificados, contraseñas, hashes y archivos derivados se generan en
`wazuh/runtime`, fuera del control de versiones. La configuración declarativa,
las reglas, las pruebas y los scripts sí se versionan.

## Consecuencias

- La aplicación puede seguir arrancando de forma independiente.
- Un fallo o reinicio de Wazuh no elimina PostgreSQL ni interrumpe SanoliFood.
- El tribunal puede reproducir el stack con objetivos Make documentados.
- La topología single-node no representa alta disponibilidad; esta limitación se
  declarará en la memoria y se propondrá un despliegue multinodo como línea futura.
- Los agentes Ubuntu y Windows se incorporarán en el siguiente incremento sin
  modificar el stack central.
