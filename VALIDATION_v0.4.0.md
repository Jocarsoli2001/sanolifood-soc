# Validación previa — SanoliFood SOC v0.4.0

Fecha: 2026-08-19

## Comprobaciones ejecutadas fuera del laboratorio

- 28 pruebas Python aprobadas con Python 3.12.13 y dependencias bloqueadas.
- Todos los scripts `.sh` superan `bash -n`.
- `compose.yaml`, `wazuh/compose.yaml`, generador de certificados y archivos de
  configuración superan el parseo YAML.
- `ossec.conf` y `sanolifood_rules.xml` superan el parseo XML.
- `uv.lock` fue regenerado para SanoliFood 0.4.0.
- No se incluyen certificados, claves privadas, `.env` ni contraseñas reales.
- La configuración Wazuh se deriva de la etiqueta oficial 4.14.7 fijada al
  commit `adcc5b57d2f7edfcbe6c399272dc76fbdf12b623`.
- La invocación aislada de `hash.sh` declara explícitamente el `JAVA_HOME`
  incluido en la imagen. Esto es necesario porque `--entrypoint` omite la
  exportación realizada por el entrypoint normal de Wazuh Indexer.

## Validaciones deliberadamente pendientes

El entorno de construcción no dispone de un daemon Docker. Por tanto, estas
comprobaciones se ejecutan obligatoriamente en `sanolifoodsochost`:

```bash
make wazuh-preflight
make upgrade-0.4
make soc-health
make wazuh-test-rules
make test
```

No debe considerarse cerrado el incremento hasta capturar sus resultados reales
en `WAZ-001`.
