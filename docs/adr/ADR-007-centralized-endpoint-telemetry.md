# ADR-007: telemetría de endpoint con políticas Wazuh centralizadas

- Estado: Aceptada
- Fecha: 2026-08-22

## Contexto

El laboratorio necesita complementar los eventos de aplicación y red con
telemetría de host verificable en Ubuntu y Windows. La configuración local e
independiente de cada agente dificultaría la reproducción, el control de cambios
y la demostración ante terceros.

## Decisión

Se emplean dos grupos Wazuh, `sanolifood-linux` y `sanolifood-windows`, cuyas
políticas `agent.conf` se versionan en el repositorio y se publican desde el
manager. Ambos agentes usan Wazuh 4.14.7 y el transporte seguro del manager por
1514/TCP. Windows incorpora Sysmon 15.21 con una configuración acotada y
versionada; los binarios externos deben tener firma Authenticode válida y sus
hashes se registran durante el despliegue.

Las pruebas en vivo escriben únicamente marcadores en rutas sintéticas de
SanoliFood. La contraseña de enrolamiento se genera localmente, permanece fuera
de Git y no se incorpora a manifiestos ni evidencias.

## Consecuencias

- Las políticas defensivas pueden revisarse, probarse y reproducirse desde Git.
- Los cambios de configuración empresarial generan FIM en ambos sistemas.
- Sysmon amplía la visibilidad de procesos y conexiones internas de Windows.
- El manager y las dos VMs deben compartir el segmento aislado del laboratorio.
- Las políticas requieren tuning adicional antes de cualquier uso productivo.
