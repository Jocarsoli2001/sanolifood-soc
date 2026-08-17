# Hotfix 0.2.1 — reconstrucción limpia y verificable

## Por qué existe este hotfix

El despliegue anterior podía combinar una imagen etiquetada como `0.1.0`, plantillas
de `0.2.0`, assets almacenados por el navegador y una base marcada por Alembic sin
las tablas físicas correspondientes. Este paquete elimina esos estados ambiguos.

## Correcciones incorporadas

- Imagen única `sanolifood/app:0.2.1`.
- CSS y JavaScript con parámetro de versión.
- `Cache-Control: no-store` para assets durante desarrollo y pruebas.
- Comprobación de `alembic_version`, `platform_metadata`, `users` y `audit_events`
  antes de crear el administrador.
- Healthcheck del proxy contra `/health/ready`.
- Reconstrucción completa del stack para que Nginx resuelva el contenedor actual.

## Importación

Desde PowerShell:

```powershell
scp "D:\Descargas\SanoliFood_Increment_v0.2.1.zip" socadmin@IP_DE_LA_VM:/home/socadmin/
```

En Ubuntu:

```bash
cd ~/sanolifood-soc
IMPORT_DIR="$(mktemp -d)"
unzip ~/SanoliFood_Increment_v0.2.1.zip -d "$IMPORT_DIR"
cp -a "$IMPORT_DIR/SanoliFood_Increment_v0.2.1/." .
chmod +x app/entrypoint.sh infrastructure/scripts/*.sh
```

## Reinicio destructivo autorizado del laboratorio

Este procedimiento elimina únicamente los contenedores, redes y volúmenes
declarados en `compose.yaml`. Se perderán los usuarios y eventos actuales de la
base SanoliFood, algo esperado en este reinicio inicial.

```bash
cd ~/sanolifood-soc
./infrastructure/scripts/reset-lab.sh --confirm
```

El script genera secretos locales nuevos, elimina el volumen de PostgreSQL,
construye `0.2.1` sin caché, espera los healthchecks y ejecuta las pruebas. Al
terminar muestra una contraseña inicial que debe guardarse fuera de Git.

## Verificación final

```bash
docker compose ps
docker compose images
make health
make test
curl -fsS http://127.0.0.1:8080/auth/login | grep -o 'app.css[^" ]*'
curl -fsS 'http://127.0.0.1:8080/static/css/app.css?v=0.2.1' | sha256sum
```

Resultados esperados:

- `postgres`, `app` y `nginx` aparecen `healthy`.
- La imagen es `sanolifood/app:0.2.1`.
- Las pruebas finalizan correctamente.
- El HTML referencia `app.css?v=0.2.1`.
- El login presenta un panel corporativo oscuro y un formulario centrado.

## Regla operativa posterior

Para reconstruir código conservando los datos se utiliza `make rebuild`. Para
eliminar también la base de laboratorio se utiliza `make reset-lab`. No se debe
recrear solamente `app` mientras Nginx permanezca en ejecución.
