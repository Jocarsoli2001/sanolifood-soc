# Versiones fijadas — incremento 04

| Componente | Versión | Decisión |
|---|---:|---|
| SanoliFood Operations | 0.4.0 | Telemetría JSON persistente para SIEM |
| Wazuh manager | 4.14.7 | Misma versión en todos los componentes centrales |
| Wazuh indexer | 4.14.7 | Nodo único para el laboratorio reproducible |
| Wazuh dashboard | 4.14.7 | Interfaz HTTPS del SOC |
| Wazuh certificates generator | 0.0.4 | Herramienta oficial con `CERT_TOOL_VERSION=4.14` |
| OpenSearch JVM heap | 1 GiB | Valor oficial de la plantilla single-node |
| Docker Compose | 5.4.0 validado | Orquestación de aplicación y SOC |

Referencia de origen: etiqueta oficial `wazuh/wazuh-docker@v4.14.7`, objeto de
etiqueta `cb4c71c0b7797247c22ef067d4486d60c5e45bee` y commit resuelto
`adcc5b57d2f7edfcbe6c399272dc76fbdf12b623`.
