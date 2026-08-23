# ADR-006: Suricata como sensor IDS de borde en contenedor

## Estado

Aceptada para el hito SOC v0.5.0.

## Contexto

SanoliFood publica Nginx mediante la dirección de la VM Ubuntu y el puerto 8080.
El bridge DMZ de Docker contiene únicamente Nginx, pero observar solo ese bridge
ocultaría sondeos dirigidos a otros servicios publicados del host corporativo
simulado. Además, el identificador del bridge cambia cuando Docker recrea la red.

## Decisión

Ejecutar un contenedor Suricata con versión fijada, red del host y las
capacidades `NET_ADMIN`, `NET_RAW` y `SYS_NICE`. Un script de arranque descubre
la interfaz de la ruta predeterminada y la dirección IPv4 actual de la VM. El
sensor opera exclusivamente en modo IDS; no descarta ni modifica paquetes.

El registro EVE JSON se conserva en el volumen
`sanolifood_suricata_logs`. Wazuh monta el mismo volumen en modo de solo lectura
y analiza los eventos JSON de una línea mediante sus reglas estándar de
Suricata y las reglas hijas de SanoliFood.

## Consecuencias

- El reconocimiento externo y el tráfico hacia servicios publicados son
  observables.
- Los nombres de interfaz y las direcciones DHCP no quedan fijados en Git.
- La validación en vivo debe originarse en otra máquina, como Windows o Kali,
  porque el tráfico de loopback no atraviesa la interfaz monitorizada.
- El contenedor se limita a 1 GiB de RAM y 1.5 CPU para proteger el host.
- La visibilidad se limita al tráfico recibido o transmitido por esta VM; un TAP
  de red o mirror del switch virtual permanece como mejora futura.
