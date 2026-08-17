# Implementación 02 — Identidad, RBAC y auditoría (v0.2.1)

> Si ya se intentó desplegar `v0.2.0` o la base presenta un estado parcial,
> utiliza primero `docs/HOTFIX-02.1-clean-rebuild.md`. No repares manualmente
> contenedores aislados.

## Objetivo y trazabilidad con el TFM

El incremento añade un flujo completo de identidad útil tanto para la aplicación
empresarial como para la ingeniería de detección. Los eventos `auth.login.failed`,
`auth.account.locked` y `auth.login.succeeded` servirán posteriormente para casos de
uso relacionados con MITRE ATT&CK T1110 (Brute Force) y T1078 (Valid Accounts).

## 1. Cerrar el incremento base

Antes de importar archivos, confirma que `v0.1.0` está saludable y regístralo:

```bash
cd ~/sanolifood-soc
docker compose ps
make health
make test
git add .
git commit -m "Tarea: Completar plataforma base funcional de SanoliFood SA"
git status
```

Si el commit indica que no hay cambios, continúa. El árbol debe quedar limpio.

## 2. Transferir e importar el paquete

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

## 3. Configurar secretos e identidad inicial

El siguiente bloque solo añade las variables si aún no existen:

```bash
cd ~/sanolifood-soc
sed -i 's/^APP_VERSION=.*/APP_VERSION=0.2.1/' .env

if ! grep -q '^SESSION_SECRET=' .env; then
  SESSION_SECRET_VALUE="$(openssl rand -hex 32)"
  ADMIN_PASSWORD_VALUE="Sf!$(openssl rand -hex 12)Aa1"
  {
    printf '\nSESSION_SECRET=%s\n' "$SESSION_SECRET_VALUE"
    printf 'SESSION_MAX_AGE_SECONDS=28800\n'
    printf 'LOGIN_MAX_ATTEMPTS=5\n'
    printf 'LOGIN_LOCKOUT_SECONDS=900\n'
    printf 'BOOTSTRAP_ADMIN_USERNAME=admin.sanolifood\n'
    printf 'BOOTSTRAP_ADMIN_EMAIL=admin@sanolifood.local\n'
    printf 'BOOTSTRAP_ADMIN_FULL_NAME=Administrador SanoliFood\n'
    printf 'BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$ADMIN_PASSWORD_VALUE"
  } >> .env
  printf '\nGuarda estas credenciales ahora:\nUsuario: admin.sanolifood\nContraseña: %s\n' "$ADMIN_PASSWORD_VALUE"
  unset SESSION_SECRET_VALUE ADMIN_PASSWORD_VALUE
fi

git check-ignore .env
```

`git check-ignore .env` debe imprimir `.env`. No compartas el archivo ni pegues su
contenido en capturas o evidencias.

## 4. Construir y migrar

```bash
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
make health
make test
```

La primera ejecución aplica ambas migraciones y crea el administrador. El resultado
esperado es `13 passed` y tres servicios saludables.

## 5. Validación funcional

1. Abre `http://IP_DE_LA_VM:8080`.
2. Comprueba que `/` redirige a la pantalla de acceso.
3. Ingresa con `admin.sanolifood` y la contraseña generada.
4. Abre **Usuarios** y crea `quality.operator` con rol Calidad.
5. Abre **Auditoría** y confirma los eventos de login y creación.
6. Cierra sesión e intenta acceder con el nuevo usuario.
7. Confirma que el usuario de Calidad no puede abrir `/users`.

Verificación directa sin mostrar secretos:

```bash
docker compose exec postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select username, role, is_active from users order by id;"'

docker compose exec postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select event_type, outcome, actor_username, source_ip from audit_events order by id desc limit 10;"'
```

Después de comprobar que el administrador existe, puedes retirar el secreto de
bootstrap del entorno sin alterar su contraseña almacenada:

```bash
sed -i 's/^BOOTSTRAP_ADMIN_PASSWORD=.*/BOOTSTRAP_ADMIN_PASSWORD=/' .env
make rebuild
```

## 6. Evidencia IAM-001

```bash
mkdir -p evidence/IAM-001
docker compose ps > evidence/IAM-001/compose-status.txt
make test > evidence/IAM-001/automated-tests.txt 2>&1
curl -sS -D evidence/IAM-001/login-headers.txt -o /dev/null http://127.0.0.1:8080/auth/login
docker compose logs --no-color --tail=250 app > evidence/IAM-001/security-events.jsonl
```

Capturas recomendadas:

- `login.png`
- `users-rbac.png`
- `audit-events.png`
- `permission-denied.png`

No incluyas contraseñas, cookies ni el archivo `.env`.

## 7. Commit

```bash
git status --short
git add .
git commit -m "Tarea: Implementar identidad RBAC y auditoría en SanoliFood"
git status
git log --oneline --decorate -3
```

## Criterios de finalización

- Los tres contenedores están saludables.
- Las nueve pruebas terminan correctamente.
- Un visitante no autenticado es redirigido al login.
- El administrador puede crear y desactivar usuarios.
- Un rol sin privilegios recibe HTTP 403 en `/users`.
- Cinco contraseñas erróneas bloquean temporalmente la cuenta.
- Los eventos se guardan en PostgreSQL y aparecen como JSON en los logs.
- La evidencia `IAM-001` está registrada y Git queda limpio.
