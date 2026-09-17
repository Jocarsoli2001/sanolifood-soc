# SanoliFood SOC

Laboratorio SOC reproducible para una empresa ficticia de procesamiento de
alimentos. Integra una aplicación empresarial, Wazuh, Suricata y n8n para
cubrir un flujo defensivo completo: generación de eventos, recolección de
telemetría, detección, revisión humana, respuesta temporal, rollback y
conservación de evidencias.

La infraestructura central se despliega con Docker Compose sobre Ubuntu. El
laboratorio utiliza tres máquinas virtuales: Ubuntu SOC, Windows y Kali Linux.
Ubuntu y Windows aportan telemetría real mediante agentes Wazuh; Kali funciona
como origen controlado de los escenarios de evaluación.

> [!CAUTION]
> Este proyecto debe utilizarse exclusivamente en un laboratorio propio,
> aislado y autorizado. Los escenarios incluidos solo admiten activos
> privados dentro de la red `10.20.0.0/24`.

> [!IMPORTANT]
> Para reproducir una entrega evaluada, utilice el tag indicado en la memoria
> del TFM y siga el README contenido en ese mismo tag. No mezcle archivos,
> evidencias ni resultados procedentes de versiones diferentes.

---

## Elegir una ruta de despliegue

El laboratorio puede ponerse en funcionamiento de dos maneras. Ambas conducen
al mismo entorno y permiten ejecutar las mismas verificaciones.

| Ruta | Cuándo utilizarla | Tiempo y alcance |
| --- | --- | --- |
| [Ruta 1: instalación completa desde cero](#ruta-1-instalación-completa-desde-cero) | Para reconstruir y auditar cada componente | Incluye creación de VMs, red, Docker, servicios y endpoints |
| [Ruta 2: tres VMs preconfiguradas](#ruta-2-puesta-en-marcha-desde-tres-vms-preconfiguradas) | Para revisar rápidamente el sistema ya desplegado | Requiere importar las VMs, comprobar la red y levantar los servicios |

Una vez completada cualquiera de las rutas, continúe con la
[prueba rápida de verificación](#prueba-rápida-de-verificación) o con la
[campaña completa de evaluación](#campaña-completa-de-evaluación).

### Navegación rápida

- [Arquitectura del laboratorio](#arquitectura-del-laboratorio)
- [Abrir las interfaces](#abrir-las-interfaces)
- [Cómo usar Wazuh Dashboard](#cómo-usar-wazuh-dashboard)
- [Cómo usar n8n y SOAR](#cómo-usar-n8n-y-soar)
- [Encender, apagar y revisar el sistema](#encender-apagar-y-revisar-el-sistema)
- [Resolución de problemas](#resolución-de-problemas)
- [Resultado validado incluido](#resultado-validado-incluido)

---

## Ruta 1: instalación completa desde cero

Esta ruta reconstruye el laboratorio completo y permite auditar todas las
decisiones de instalación. Siga las secciones en este orden:

1. [Preparar las máquinas virtuales](#preparar-las-máquinas-virtuales).
2. [Instalar Docker Engine y Docker Compose](#instalar-docker-engine-y-docker-compose).
3. [Instalar SanoliFood SOC](#instalar-sanolifood-soc).
4. [Instalar los endpoints Wazuh](#instalar-los-endpoints-wazuh).
5. [Comprobar las interfaces y los servicios](#abrir-las-interfaces).
6. [Realizar la prueba rápida](#prueba-rápida-de-verificación).

Los comandos de esta ruta corresponden al procedimiento utilizado y validado
durante la construcción del laboratorio. Sustituya únicamente los nombres de
usuario, direcciones de gestión y valores marcados como variables.

---

## Ruta 2: puesta en marcha desde tres VMs preconfiguradas

Esta ruta permite comprobar el proyecto sin repetir la instalación completa.
Las máquinas ya incluyen el repositorio, la configuración del laboratorio, los
agentes y los componentes necesarios.

> **Descarga de las VMs:** [Carpeta de Google Drive con los OVAs de las VMs.](https://drive.google.com/drive/folders/1rWbaYSLhVXcdhzCWAKbr1W_5snYtm5O7?usp=sharing)

### 1. Importar las máquinas

Importe en VirtualBox las tres máquinas proporcionadas y conserve sus nombres:

- Ubuntu SOC: `10.20.0.10/24` en la red interna;
- Windows endpoint: `10.20.0.20/24` en la red interna;
- Kali de validación: `10.20.0.30/24` en la red interna.

Los usuarios de las 3 VMs pre configuradas es `socadmin` y la contraseña para estas mismas 3 VMs es `tfm`. 

Previo a encender las VMs, actualice el adaptador 1 de red (adaptador puente) para que utilice la interfaz de red de su PC.
Luego, verifique que el segundo adaptador de las tres máquinas esté conectado a la
red interna `sanolifood-lab`. En Ubuntu, mantenga **Modo promiscuo: Permitir
todo** para que Suricata pueda observar el tráfico del segmento.

### 2. Comprobar la red de Ubuntu

Encienda primero Ubuntu e inicie sesión. Compruebe sus interfaces:

```bash
ip -br address
```

La interfaz de administración `enp0s3` debe aparecer en estado `UP` y tener una
dirección IPv4 asignada. La interfaz interna `enp0s8` debe mostrar
`10.20.0.10/24`.

`ip -br address` confirma la configuración local, pero no prueba por sí solo la
salida a Internet. Si necesita descargar actualizaciones, compruébela también:

```bash
ping -c 3 1.1.1.1
curl -I https://github.com
```

Si `enp0s3` no recibe una dirección, apague la VM, revise el adaptador de
administración en VirtualBox y vuelva a iniciarla. En redes donde el modo
puente no entrega DHCP, utilice NAT para la administración o genere una nueva
dirección MAC desde la configuración avanzada del adaptador.

### 3. Comprobar los servicios y sincronizar Ubuntu

Después de iniciar Ubuntu, espere entre dos y cinco minutos para permitir que Docker restaure los contenedores configurados. Luego compruebe su estado:

```bash
cd ~/sanolifood-soc
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Si todos los contenedores esperados aparecen en ejecución y los que disponen de comprobación de salud muestran el estado healthy, no es necesario ejecutar nuevamente make soc-up.

Si falta algún contenedor o aparece en estado Exited, Restarting o unhealthy, reconcilie los servicios:

```bash
make soar-disable-live
make soar-down
make wazuh-down
make suricata-down
make down

sudo systemctl restart docker

make soc-up
```
> [!IMPORTANT]
> En caso exista algún problema al realizar make soc-up, como que la VM se quede congelada
> o no haya avance luego de un tiempo muy largo, se recomienda que se borre la VM importada con todos sus archivos
> y se re importe a VirtualBox desde la OVA descargada. Luego de esta re importación, se pueden volver a comprobar los servicios
> como lo indica el inicio del [paso 3](#3-comprobar-los-servicios-y-sincronizar-ubuntu).

Espere unos minutos y repita la comprobación:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Si necesita consultar también los contenedores detenidos, utilice:

```bash
docker ps -a
```

No ejecute make bootstrap ni reinstale los endpoints: las VMs preconfiguradas ya contienen las cuentas, los agentes, los volúmenes y la configuración necesarios.

Antes de encender Windows y Kali, vuelva a sincronizar el reloj de Ubuntu:

```bash
sudo systemctl restart chrony
sudo chronyc makestep
chronyc tracking
```

La salida de chronyc tracking debe mostrar Leap status : Normal. Ubuntu funciona como servidor horario para las demás máquinas del laboratorio.

### 4. Encender y sincronizar Windows y Kali

Cuando los servicios centrales estén disponibles, encienda Windows y Kali y espere a que ambos sistemas terminen de iniciar.

En Kali, sincronice el reloj con Ubuntu:

```bash
sudo systemctl restart systemd-timesyncd
sudo timedatectl set-ntp true
timedatectl timesync-status
```

El servidor indicado debe ser 10.20.0.10.

En Windows, abra PowerShell como administrador y fuerce una nueva sincronización:

```bash
w32tm /resync /rediscover
Start-Sleep -Seconds 5
w32tm /query /source
w32tm /query /status
```

La fuente horaria debe aparecer como 10.20.0.10.

Finalmente, desde Ubuntu compruebe la comunicación por la red interna:

```bash
ping -c 3 10.20.0.20
ping -c 3 10.20.0.30
```

Dentro de Windows y Kali confirme que mantienen, respectivamente, las direcciones 10.20.0.20/24 y 10.20.0.30/24. Si una VM no responde, revise que su segundo adaptador esté conectado a la red interna sanolifood-lab y que esa interfaz no tenga puerta de enlace ni DNS configurados. 

En caso que Ubuntu no pueda realizar ping a Windows, realizar el siguiente comando desde una ventana de Powershell como administrador:

```bash
New-NetFirewallRule -DisplayName "SanoliFood Lab - ICMPv4" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -RemoteAddress 10.20.0.0/24 -Action Allow
```

Luego de esto, comprobar nuevamente la conexión a Windows y Kali:

```bash
ping -c 3 10.20.0.20
ping -c 3 10.20.0.30
```

### 5. Verificar que el sistema esté disponible

De vuelta en Ubuntu, ejecute:

```bash
make soc-health
make endpoint-health
make soar-health
```

La comprobación debe mostrar los servicios centrales saludables y los agentes
`sanolifood-ubuntu-01` y `sanolifood-win-01` en estado `active`.

Obtenga la dirección de gestión de Ubuntu con `ip -br address` y abra:

- SanoliFood Operations: `http://IP_DE_GESTION_DE_UBUNTU:8080`;
- Wazuh Dashboard: `https://IP_DE_GESTION_DE_UBUNTU:8443`;
- n8n: `http://127.0.0.1:5678` luego de levantar el túnel SSH descrito en
  [Preparar n8n](#5-preparar-n8n).

Con las tres VMs conectadas ya puede ejecutar el
[preflight de evaluación](#1-preflight), revisar la aplicación, consultar las
alertas en Wazuh y repetir los escenarios documentados.

---

## Qué incluye

| Componente | Función |
| --- | --- |
| SanoliFood Operations | Aplicación web con identidades, inventario, producción, calidad y auditoría |
| Wazuh | Recepción, análisis, correlación e interfaz de alertas |
| Suricata | Inspección de tráfico y telemetría IDS/NDR en formato EVE JSON |
| Wazuh Agent para Ubuntu | Eventos del host y control de integridad de archivos |
| Wazuh Agent + Sysmon para Windows | Telemetría de endpoint y FIM con WhoData |
| n8n | Coordinación de los flujos de respuesta |
| Controlador SOAR | Incidentes, acciones, aprobaciones, métricas y rollback |
| PostgreSQL | Datos de la aplicación y del sistema SOAR |
| Kali Linux | Generación de eventos de prueba limitados al laboratorio |

El repositorio contiene cinco workflows de n8n, nueve playbooks SOAR y catorce
reglas conectadas con SOAR. La campaña final contiene ocho escenarios diferentes y
permite medir los tiempos entre el inicio de la prueba, Wazuh y SOAR.

---

## Arquitectura del laboratorio

```mermaid
flowchart TD
    K["Kali 10.20.0.30"] -->|"Pruebas HTTP"| A["Aplicación 10.20.0.10:8080"]
    K -->|"Tráfico observado"| S["Suricata IDS/NDR"]
    E["Ubuntu y Windows"] -->|"Eventos de endpoint"| W["Wazuh"]
    A -->|"Eventos de negocio"| W
    S -->|"EVE JSON"| W
    W -->|"Alerta seleccionada"| N["n8n y controlador SOAR"]
    N -->|"Acción aprobada"| A
```

Servicios centrales administrados por Compose:

- aplicación, Nginx y PostgreSQL;
- Wazuh manager, indexer y dashboard;
- sensor Suricata;
- n8n, controlador SOAR y PostgreSQL SOAR.

Componentes externos necesarios para validar telemetría real:

- agente Wazuh nativo en Ubuntu;
- agente Wazuh y Sysmon nativos en Windows;
- Kali como cliente de prueba.

---

## Versiones principales

| Componente | Versión utilizada |
| --- | ---: |
| [Ubuntu Server](https://ubuntu.com/download/server) | 24.04 LTS |
| [Windows](https://go.microsoft.com/fwlink/?LinkId=2265055) para endpoint | 10 (instalar en idioma inglés) a través de la herramienta `Media Creation Tool` para la creación del ISO|
| [Kali Linux](https://www.kali.org/get-kali/#kali-virtual-machines) | Imagen oficial para VirtualBox |
| Python | 3.12.11 |
| FastAPI | 0.116.1 |
| PostgreSQL | 17.6 |
| Nginx | 1.28.0 |
| Wazuh | 4.14.7 |
| Wazuh Agent | 4.14.7 |
| Suricata | 8.0.6 |
| Sysmon | 15.22 |
| n8n | 2.36.7 |

---

## Recursos recomendados

| Máquina | CPU | Memoria | Disco | Uso |
| --- | ---: | ---: | ---: | --- |
| Ubuntu SOC | 4 vCPU | 10–12 GiB | 120 GiB | Contenedores y agente Linux |
| Windows | 2 vCPU | 4 GiB | 40 GiB | Endpoint Windows |
| Kali | 2 vCPU | 4 GiB | 30 GiB | Pruebas controladas |

Para mantener las tres VMs encendidas al mismo tiempo se recomienda un equipo
con al menos 24 GiB de RAM. Con menos memoria, Windows y Kali pueden encenderse
solo cuando su prueba lo requiera.

---

## Preparar las máquinas virtuales

Para preparar las VMs del laboratorio:

1. Instale [Oracle VirtualBox](https://www.virtualbox.org/wiki/Downloads).
2. Descargue las versiones indicadas en
   [Versiones principales](#versiones-principales):
   - Kali Linux: imagen oficial preparada para VirtualBox;
   - Ubuntu Server: imagen ISO de Ubuntu Server 24.04 LTS;
   - Windows: imagen ISO de Windows 10 creada a través de `Media Creation Tool`, la cual permite crear un archivo ISO para nuestra VM. Es obligatorio
     instalar Windows en inglés para que los nombres usados por los comandos
     de PowerShell coincidan con esta guía.
3. Asigne a cada VM los recursos descritos en
   [Recursos recomendados](#recursos-recomendados).

Puede utilizar nombres como `sanolifood-ubuntu-01`, `sanolifood-win-01` y
`sanolifood-kali-01`. Elija como usuario (para las 3 VMs): `socadmin` y como contraseña: `tfm`. Mantenga la configuración
de firmware propuesta por VirtualBox para cada sistema operativo; el proyecto
no exige cambiar manualmente EFI en Ubuntu o Kali.

### Red de VirtualBox

Cree una red interna con el nombre exacto `sanolifood-lab`. Con cada VM apagada,
abra **Configuración > Red** y habilite dos adaptadores. El primer adaptador se
usa para administración y acceso a Internet; el segundo, para el laboratorio.
Las direcciones `10.20.0.x` se configuran dentro de cada sistema operativo, no
desde VirtualBox.

| VM | Adaptador 1 | Adaptador 2 | Dirección del adaptador 2 |
| --- | --- | --- | --- |
| Ubuntu SOC | Puente para administración | Red interna `sanolifood-lab` | `10.20.0.10/24` |
| Windows | Puente para administración | Red interna `sanolifood-lab` | `10.20.0.20/24` |
| Kali | Puente para administración | Red interna `sanolifood-lab` | `10.20.0.30/24` |

El modo puente facilita el acceso desde el equipo anfitrión. Si la red física
no entrega una dirección por DHCP —algo que puede ocurrir con algunos
adaptadores Wi-Fi—, apague la VM y pruebe una de estas alternativas:

1. genere una nueva dirección MAC desde las opciones avanzadas del adaptador;
2. vuelva a seleccionar el adaptador físico correcto;
3. utilice NAT temporalmente para instalar paquetes.

El tráfico entre Ubuntu, Windows y Kali siempre debe circular por el segundo
adaptador `sanolifood-lab`, por lo que este no debe tener gateway ni DNS.

En el adaptador 2 de Ubuntu seleccione **Modo promiscuo: Permitir todo**. Esto
permite que Suricata vea el tráfico del segmento interno. No configure puerta
de enlace ni DNS en los adaptadores internos.

La guía utiliza estos nombres de interfaz:

- Ubuntu: `enp0s3` para administración y `enp0s8` para el laboratorio;
- Kali: `eth0` para administración y `eth1` para el laboratorio.

Compruebe los nombres reales con `ip -br address` antes de continuar.

### Configurar Ubuntu SOC

En Ubuntu, cree un archivo Netplan para la interfaz interna:

```bash
touch /etc/netplan/99-sanolifood-lab.yaml
sudo chmod 600 /etc/netplan/99-sanolifood-lab.yaml

# Editar archivo
sudo nano /etc/netplan/99-sanolifood-lab.yaml
sudo vi /etc/netplan/99-sanolifood-lab.yaml
```

Contenido:

```yaml
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: false
      addresses:
        - 10.20.0.10/24
```

Aplique la configuración:

```bash
sudo netplan try
sudo netplan apply
ip -br address
```

El resultado debe mostrar `10.20.0.10/24` en `enp0s8`.

Instale SSH y las utilidades necesarias:

```bash
sudo apt update
sudo apt install -y openssh-server git make curl openssl iproute2 ca-certificates chrony
sudo systemctl enable --now ssh chrony
```

La campaña compara marcas de tiempo de tres equipos. Ubuntu será la fuente de
hora del laboratorio. Cree esta configuración:

```bash
sudo install -d -o root -g root -m 0755 /etc/chrony/conf.d
sudo nano /etc/chrony/conf.d/sanolifood-lab.conf
```

Contenido:

```text
allow 10.20.0.0/24
local stratum 10
```

Compruebe que Chrony carga el directorio de configuración adicional. De lo
contrario, el archivo recién creado no tendrá efecto:

```bash
grep -E 'confdir|include' /etc/chrony/chrony.conf
```

Si este comando no devuelve ningún resultado, agregue la línea
`confdir /etc/chrony/conf.d` al final de `/etc/chrony/chrony.conf` y guarde los
cambios.

Reinicie Chrony y compruebe su estado:

```bash
sudo systemctl restart chrony
chronyc tracking
sudo ss -lunp | grep -E ':123\b'
```

`chronyc tracking` debe mostrar `Leap status : Normal`; la sincronización puede
tardar unos segundos. El comando `ss` debe mostrar a `chronyd` escuchando por
UDP en el puerto `123`, normalmente sobre `0.0.0.0:123`, `[::]:123` o la
dirección interna de Ubuntu.

Si UFW está instalado y activo, permita NTP únicamente desde la red interna:

```bash
if command -v ufw >/dev/null && sudo ufw status | grep -q '^Status: active'; then
  sudo ufw allow in on enp0s8 from 10.20.0.0/24 to any port 123 proto udp
fi
```

### Configurar Windows

En las propiedades IPv4 del segundo adaptador configure:

- dirección IP: `10.20.0.20`;
- máscara: `255.255.255.0`;
- puerta de enlace: vacía;
- DNS: vacío.

Para hacer esto, abra PowerShell como administrador e identifique el nombre de la segunda
interfaz de red utilizada por la máquina virtual:

```powershell
Get-NetAdapter
$Interface = "Nombre_Segunda_Interfaz"
```

Configure la dirección estática:

```powershell
Set-NetIPInterface -InterfaceAlias $Interface -Dhcp Disabled
New-NetIPAddress -InterfaceAlias $Interface -IPAddress 10.20.0.20 -PrefixLength 24
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixLength
```

Verifique que la segunda interfaz muestre `10.20.0.20`, mientras que la primera
mantiene una dirección de administración, por ejemplo `192.168.x.x`. Después
instale OpenSSH Server:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

Configure el servicio:

```powershell
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Get-Service sshd
```

Si `Add-WindowsCapability` no consigue instalar OpenSSH, utilice como alternativa
[Chocolatey](https://chocolatey.org/install) y ejecute:

```powershell
choco install openssh -params "'/SSHServerFeature /SSHAgentFeature'" -y
```

Después repita los comandos de configuración de `sshd`. El estado esperado del
servicio es `Running`.

Active también el servicio de hora de Windows:

```powershell
Get-Service W32Time
Set-Service -Name W32Time -StartupType Automatic
Start-Service W32Time
Get-Service W32Time
```

Con Ubuntu encendido y `W32Time` en ejecución, configure Windows para tomar la
hora desde Ubuntu:

```powershell
w32tm /config /manualpeerlist:"10.20.0.10,0x8" /syncfromflags:manual /update
Restart-Service W32Time -Force
w32tm /resync /rediscover
Start-Sleep -Seconds 5
w32tm /query /source
w32tm /query /status
```

La fuente mostrada debe comenzar con `10.20.0.10`.

Para que Ubuntu pueda comprobar la conectividad con Windows, revise el perfil de
red del segundo adaptador. Windows Defender Firewall puede bloquear ICMPv4
cuando la interfaz está clasificada como pública:

```powershell
Get-NetConnectionProfile
```

Si `NetworkCategory` es `Public`, cambie únicamente el adaptador interno a
`Private`:

```powershell
Set-NetConnectionProfile -InterfaceAlias "<alias_segunda_interfaz>" -NetworkCategory Private
```

Después habilite las reglas de eco ICMPv4:

```powershell
Get-NetFirewallRule -DisplayName "*Echo Request*ICMPv4-In*" | Enable-NetFirewallRule
```

Los nombres visibles de las reglas pueden variar con el idioma de Windows. Esta
guía se validó con Windows instalado en inglés; en otra localización, compruebe
el nombre equivalente antes de habilitar una regla.

Con esto listo, ahora debería ser posible que Ubuntu compruebe la conexión:

```bash
ping -c 3 10.20.0.20
ssh socadmin@10.20.0.20
```

### Configurar Kali Linux

En Kali identifique el nombre de la conexión asociada a `eth1`:

```bash
ip -br address
nmcli -f NAME,DEVICE,TYPE connection show --active
```

En los siguientes comandos sustituya `Wired connection 1` si su conexión tiene
otro nombre:

```bash
sudo nmcli connection modify "Wired connection 1" \
  connection.interface-name eth1 \
  ipv4.method manual \
  ipv4.addresses 10.20.0.30/24 \
  ipv4.gateway "" \
  ipv4.dns "" \
  ipv4.never-default yes \
  ipv6.method disabled

sudo nmcli connection down "Wired connection 1"
sudo nmcli connection up "Wired connection 1"
```

Compruebe la configuración de la subred:

```bash
ip -br address
ip route
```

Instale y active SSH:

```bash
sudo apt update
sudo apt install -y openssh-server python3 curl
sudo systemctl enable --now ssh
sudo systemctl is-active ssh
```

El último comando debe mostrar `active`.

Configure la sincronización horaria con Ubuntu:

```bash
sudo install -d -o root -g root -m 0755 /etc/systemd/timesyncd.conf.d
sudo touch /etc/systemd/timesyncd.conf.d/sanolifood-lab.conf

# Editar archivo
sudo nano /etc/systemd/timesyncd.conf.d/sanolifood-lab.conf
sudo vi /etc/systemd/timesyncd.conf.d/sanolifood-lab.conf
```

Contenido:

```ini
[Time]
NTP=10.20.0.10
FallbackNTP=
PollIntervalMinSec=16
PollIntervalMaxSec=64
```

Aplique y compruebe:

```bash
sudo systemctl enable --now systemd-timesyncd
sudo systemctl restart systemd-timesyncd
sudo timedatectl set-ntp true
timedatectl status
timedatectl timesync-status
```

El estado debe indicar `System clock synchronized: yes` y el servidor debe ser
`10.20.0.10`.

Cuando Ubuntu ya tenga la aplicación levantada, Kali debe poder consultarla.
Si todavía no ha desplegado SanoliFood SOC, omita esta comprobación y vuelva a
ella después de ejecutar `make soc-up`:

```bash
ping -c 3 10.20.0.10
curl --noproxy '*' -fsS http://10.20.0.10:8080/health/ready
```

---

## Instalar Docker Engine y Docker Compose

Ejecute esta sección en Ubuntu SOC. Los comandos usan el repositorio oficial de
Docker para Ubuntu 24.04.

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Active Docker y pruebe la instalación:

```bash
sudo systemctl enable --now docker
sudo docker run --rm hello-world
docker compose version
```

Para usar Docker sin escribir `sudo` en cada comando:

```bash
sudo usermod -aG docker "$USER"
```

Cierre la sesión de Ubuntu y vuelva a entrar. Después confirme:

```bash
docker info
docker compose version
```

El grupo `docker` permite administrar el sistema con privilegios equivalentes
a root. Solo deben pertenecer a él las cuentas autorizadas para operar el
laboratorio.

Confirme que la cuenta actual pertenece al grupo y puede comunicarse con el
daemon sin `sudo`:

```bash
id -nG
docker info
```

La salida de `id -nG` debe incluir `docker`. Si acaba de agregar el grupo,
cierre la sesión de Ubuntu y vuelva a entrar antes de continuar.

Prepare el requisito del indexer Wazuh:

```bash
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-sanolifood.conf
sudo sysctl --system
sysctl vm.max_map_count
```

El último comando debe devolver al menos `262144`.

---

## Instalar SanoliFood SOC

### 1. Descargar el repositorio

Dentro de Ubuntu, navegue al directorio `~` y clone el repositorio de
SanoliFood SOC. Para reproducir los resultados del TFM, sustituya
`TAG_EVALUADO` por el tag publicado en la memoria:

```bash
git clone https://github.com/Jocarsoli2001/sanolifood-soc.git
cd sanolifood-soc
git checkout TAG_EVALUADO
git status -sb
```

El estado debe mostrar el tag seleccionado sin cambios locales. La rama `main`
puede contener trabajo posterior y no debe utilizarse para verificar cifras de
una entrega ya cerrada.

### 2. Crear la configuración local

`make bootstrap` crea la configuración local a partir de las plantillas. El
bloque siguiente genera valores aleatorios distintos para la sesión, la base
de datos y el administrador inicial, y los escribe únicamente en `.env`:

```bash
make bootstrap

SESSION_SECRET_VALUE="$(openssl rand -hex 32)"
POSTGRES_PASSWORD_VALUE="$(openssl rand -hex 24)"
ADMIN_PASSWORD_VALUE="Sf-$(openssl rand -hex 12)-Aa1"

sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=${SESSION_SECRET_VALUE}|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VALUE}|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://sanolifood_app:${POSTGRES_PASSWORD_VALUE}@postgres:5432/sanolifood|" .env
sed -i "s|^BOOTSTRAP_ADMIN_PASSWORD=.*|BOOTSTRAP_ADMIN_PASSWORD=${ADMIN_PASSWORD_VALUE}|" .env

printf 'Usuario inicial: admin.sanolifood\n'
printf 'Contraseña inicial: %s\n' "$ADMIN_PASSWORD_VALUE"
printf 'Guarde esta contraseña en un lugar privado.\n'

unset SESSION_SECRET_VALUE POSTGRES_PASSWORD_VALUE ADMIN_PASSWORD_VALUE
git check-ignore .env
```

`git check-ignore .env` debe devolver `.env`. No publique este archivo.

### 3. Comprobar requisitos

Verifique los requisitos dentro de Ubuntu antes de continuar:

```bash
make config
make wazuh-preflight
make suricata-preflight
make soar-static-check
```

Corrija cualquier `FAIL` antes de continuar, utilizando la sección [resolución de problemas](#resolución-de-problemas). En una instalación completamente
nueva, una comprobación puede indicar que `dmz_network` todavía no existe. En
ese caso cree primero la plataforma base y repita las comprobaciones:

```bash
make up
make config
make wazuh-preflight
make suricata-preflight
make soar-static-check
```

Si una contraseña fue escrita de forma distinta en `POSTGRES_PASSWORD` y
`DATABASE_URL`, corrija `.env` antes del primer arranque completo. No elimine
volúmenes para ocultar un error de configuración; utilice el procedimiento de
[reinicio completo](#reinicio-completo-del-laboratorio) únicamente cuando
quiera descartar deliberadamente los datos del laboratorio.

### 4. Levantar la infraestructura central

```bash
SURICATA_INTERFACE_OVERRIDE=enp0s8 \
SURICATA_HOME_NET_OVERRIDE=10.20.0.0/24 \
make soc-up
```

El primer arranque descarga varias imágenes y puede tardar algunos minutos.
Si ejecutó `make up` en el paso anterior, `make soc-up` conserva los volúmenes
y reconcilia la plataforma base con el resto del SOC. Los siguientes arranques
reutilizan las imágenes y volúmenes existentes.

`make soc-up` inicia los servicios centrales. Todavía falta crear la cuenta
propietaria de n8n y registrar los endpoints.

### 5. Preparar n8n

n8n solo escucha en `127.0.0.1` dentro de Ubuntu. Obtenga primero la dirección
de administración asignada a `enp0s3`:

```bash
ip -br address
```

Desde el equipo con el que administra las VMs, abra un túnel SSH hacia esa
dirección y mantenga la consola abierta:

```bash
ssh -L 5678:127.0.0.1:5678 usuario_ubuntu@IP_DE_GESTION_DE_UBUNTU
```

Abra `http://127.0.0.1:5678`, cree la primera cuenta propietaria de n8n y
complete el asistente inicial. Después, en Ubuntu, publique los cinco
workflows:

```bash
make soar-install-workflows
make soar-health
make soar-validate-live
```

El resultado correcto indica:

- `n8n` y `soar-controller` en estado `healthy`;
- cinco workflows presentes y publicados;
- `response_mode=dry-run`;
- evidencia automática completada;
- respuesta simulada, sin bloquear nada todavía.

### 6. Comprobar los servicios antes de instalar endpoints

No use aún `make soc-health`, porque ese comando también exige los agentes
Ubuntu y Windows. En esta fase use:

```bash
make health
make wazuh-health
make suricata-health
make soar-health
make validate
make wazuh-test-rules
make suricata-test-rules
```

Todos los servicios deben aparecer como `running` y `healthy`. Las pruebas
automatizadas deben terminar sin fallos. `make validate` puede emitir avisos
informativos; revíselos y continúe únicamente si no aparece ningún `FAIL` ni
un error que afecte a la instalación. Un aviso no debe ignorarse solo por estar
clasificado como `warning`.

---

## Instalar los endpoints Wazuh

### 1. Preparar Wazuh para la red interna

Con Windows encendido y accesible por SSH, ejecute en Ubuntu:

```bash
make endpoint-preflight
make upgrade-0.6
```

Este paso fija Suricata en `enp0s8`, limita los puertos de agentes a
`10.20.0.10`, crea los grupos `sanolifood-linux` y `sanolifood-windows` y
publica sus políticas centrales.

### 2. Instalar el agente en Ubuntu

```bash
make endpoint-install-ubuntu
sudo systemctl status wazuh-agent --no-pager
```

### 3. Copiar el instalador a Windows

Desde Ubuntu, ejecute:

```bash
make endpoint-stage-windows \
  WINDOWS_SSH=socadmin@10.20.0.20
```

Cuando se solicite, escriba la contraseña de la cuenta Windows.

Consulte y tome nota de la contraseña de registro Wazuh en la consola de Ubuntu:

```bash
make endpoint-registration-password
```

### 4. Ejecutar el instalador en Windows

Abra PowerShell como administrador dentro de Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "$env:USERPROFILE\SanoliFood-Endpoint\Install-SanoliFoodEndpoint.ps1"
```

Introduzca la contraseña de registro de Wazuh obtenida en el paso
[Copiar el instalador a Windows](#3-copiar-el-instalador-a-windows) cuando
aparezca la solicitud segura. El script instala el agente Wazuh, Sysmon y las
políticas incluidas en el repositorio.

### 5. Confirmar los endpoints

Espere hasta un minuto y ejecute en Ubuntu:

```bash
make endpoint-health
make soc-health
```

El resultado esperado incluye:

- `sanolifood-ubuntu-01` en estado `active` y grupo `sanolifood-linux`;
- `sanolifood-win-01` en estado `active` y grupo `sanolifood-windows`;
- aplicación, Wazuh, Suricata, n8n y las dos bases de datos saludables.

---

## Abrir las interfaces

Obtenga la dirección de administración de Ubuntu, normalmente asignada a
`enp0s3`:

```bash
ip -br -4 address
```

| Interfaz | Dirección |
| --- | --- |
| SanoliFood Operations | `http://IP_DE_GESTION_DE_UBUNTU:8080` |
| Wazuh Dashboard | `https://IP_DE_GESTION_DE_UBUNTU:8443` |
| n8n | `http://127.0.0.1:5678` mediante el túnel SSH ([ver instrucciones](#5-preparar-n8n)) |

Para consultar la contraseña local del dashboard Wazuh:

```bash
make wazuh-credentials
```

El usuario del dashboard es `admin`. El certificado es local y autofirmado;
compruebe la IP antes de aceptar la advertencia del navegador.

---

## Qué comprobar en SanoliFood Operations

Inicie sesión con `admin.sanolifood` y la contraseña creada durante la
[instalación](#2-crear-la-configuración-local). Revise:

- el dashboard principal;
- inventario y movimientos;
- lotes de producción;
- controles y liberaciones de calidad;
- usuarios y roles;
- auditoría.

La aplicación genera eventos JSON de negocio que Wazuh recibe desde el volumen
de logs compartido.

---

## Cómo usar Wazuh Dashboard

### Comprobar los agentes

Abra **Agents management > Summary**. Deben aparecer:

- `sanolifood-ubuntu-01`: active;
- `sanolifood-win-01`: active.

Si uno aparece desconectado, no continúe con los escenarios de endpoint.
Consulte [Resolución de problemas](#resolución-de-problemas) y recupere la
conectividad antes de continuar.

### Buscar las alertas del proyecto

Abra **Threat intelligence > Threat Hunting > Events** y seleccione un intervalo
que incluya la prueba, por ejemplo **Last 24 hours**. Añada un filtro por el
campo `rule.id` y use alguno de estos valores:

| Regla | Qué representa |
| ---: | --- |
| 110010–110012 | Acceso fallido y correlación de autenticación |
| 110020 | Ajuste alto de inventario |
| 110030 | Control de calidad fuera de especificación |
| 110100 | Validación de la ruta Suricata–Wazuh |
| 110110 | Posible exploración de servicios |
| 110120 | Enumeración de rutas web |
| 110130 | Indicador SQLi de laboratorio |
| 110140 | Tasa HTTP anómala |
| 110200 | Validación de telemetría Sysmon |
| 110210 | FIM de Ubuntu |
| 110211 | FIM WhoData de Windows |
| 110220 | Validación del endpoint Linux |

Abra una alerta y compruebe al menos:

- fecha y hora;
- `rule.id`, descripción y nivel;
- nombre del agente o fuente (`agent_name`);
- IP de origen en alertas de red (`source_ip`);
- ruta o archivo en alertas FIM (`location`);
- identificador `SF-EVAL-SCN-*` cuando la alerta provenga de la campaña de
  evaluación.

### Revisar FIM

Abra **Endpoint security > File Integrity Monitoring > Events**. Filtre por el
agente Ubuntu o Windows (`agent.name`). Los escenarios SCN-007 y SCN-008 deben
mostrar el archivo vigilado y la acción detectada.

En Windows, WhoData permite ver además información sobre el usuario o proceso
relacionado con el cambio.

### Revisar MITRE ATT&CK

Abra **Threat intelligence > MITRE ATT&CK** y seleccione el mismo intervalo de
tiempo. Después de la campaña deben aparecer técnicas asociadas a los eventos
observados, entre ellas `T1110`, `T1110.001`, `T1190`, `T1565.001` y
`T1595.002`.

### Comprobar las reglas instaladas

Abra **Server management > Rules** y busque `110100`, `110130` o cualquier otra
regla de la tabla anterior. También puede probar eventos de ejemplo desde
**Server management > Ruleset Test**.

Si no aparece una alerta reciente:

1. amplíe el intervalo de tiempo;
2. pulse actualizar;
3. confirme que el agente esté activo;
4. ejecute `make wazuh-health` y `make suricata-health` en Ubuntu;
5. consulte `make wazuh-logs` si el problema continúa.

---

## Cómo usar n8n y SOAR

En n8n abra **Workflows**. Deben existir cinco flujos publicados:

| Workflow visible en n8n | Función |
| --- | --- |
| `SF-SOAR-00 \| Orchestration Error Handler` | Registra errores de los flujos |
| `SF-SOAR-01 \| Wazuh Alert Intake and Triage` | Recibe, verifica y normaliza alertas Wazuh |
| `SF-SOAR-02 \| Analyst Decision and Response Dispatch` | Procesa aprobaciones y rechazos |
| `SF-SOAR-03 \| Expiration and Automatic Rollback` | Revierte controles al vencer su TTL |
| `SF-SOAR-04 \| Platform Health and Metrics` | Comprueba salud y actualiza métricas |

Después de generar una alerta, abra **Executions**. Una ejecución correcta debe
mostrar los nodos completados sin errores. n8n coordina el proceso; el
controlador conserva el incidente y sus acciones para que el caso no dependa
de una sola ejecución visual.

Desde Ubuntu puede ver la misma información de forma directa:

```bash
make soar-incidents
make soar-show INCIDENT_ID=UUID
make soar-metrics
```

Las respuestas posibles son:

| Acción | Resultado |
| --- | --- |
| `collect_evidence` | Guarda automáticamente el contexto del incidente |
| `app_ip_block` | Bloquea temporalmente una IP en la aplicación |
| `app_account_lock` | Bloquea temporalmente una cuenta |
| `quality_guard` | Suspende temporalmente las liberaciones de calidad |

Las acciones que cambian el funcionamiento de la aplicación requieren una
decisión humana. Esto permite revisar si la alerta corresponde a una amenaza o
a una actividad autorizada antes de aplicar el control.

---

## Prueba rápida de verificación

Esta prueba confirma la ruta completa sin cambiar el estado de la aplicación.

### 1. Preflight

Dentro de Ubuntu, ejecute el siguiente comando luego de tener las 3 máquinas levantadas:

```bash
make eval-preflight \
  KALI_SSH=socadmin@10.20.0.30 \
  WINDOWS_SSH=socadmin@10.20.0.20
```

Introduzca las contraseñas de Kali y Windows cuando se soliciten. El resultado
debe terminar en `PASS evaluation preflight` e indicar:

- SOC saludable;
- respuestas en `dry-run`;
- reenvío Wazuh habilitado;
- relojes con menos de un segundo de diferencia;
- Kali capaz de consultar la aplicación;
- Windows disponible y sincronizado.

### 2. Ruta Suricata, Wazuh y SOAR

```bash
make eval-run \
  SCENARIO=SCN-001 \
  KALI_SSH=socadmin@10.20.0.30
```

El resultado correcto es `status: PASS`, regla `110100`, evidencia automática
`completed` y `timing_integrity: valid`.

Ahora puede comprobar el mismo evento en:

- Wazuh: **Threat Hunting**, filtro `rule.id = 110100`;
- n8n: **Executions**, ejecución de entrada de alerta;
- Ubuntu: `make soar-incidents` y luego `make soar-show`.

### 3. Escenario con decisión humana

SCN-002 genera desde Kali cinco fallos de autenticación correlacionados sobre
una cuenta ficticia. Wazuh activa la regla `110011`; n8n y el controlador crean
un incidente asociado al playbook `PB-AUTH-001`; la evidencia se recopila de
forma automática; y las acciones `app_ip_block` y `app_account_lock` quedan
pendientes de una decisión humana.

Ejecute el escenario desde Ubuntu:

```bash
make eval-run \
  SCENARIO=SCN-002 \
  KALI_SSH=socadmin@10.20.0.30
```

La primera salida debe indicar `PASS_PENDING_DECISION`. En ese estado el
incidente ya fue detectado y enriquecido, pero todavía no se ha autorizado
ninguna acción sensible. Copie el `run_id` exacto mostrado y úselo en el
parámetro `RUN_ID` del siguiente comando; no escriba literalmente el valor de
ejemplo.

```bash
make eval-decide \
  RUN_ID=SF-EVAL-SCN-002-FECHA-Y-CODIGO-MOSTRADOS \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Prueba autorizada del laboratorio; se aprueban las respuestas propuestas'
```

Como la plataforma comienza en `dry-run`, las acciones deben quedar como
`simulated`. Esto prueba la detección, el incidente, la aprobación y el envío
de acciones sin bloquear al evaluador.

| Modo | Qué valida | Efecto sobre la aplicación |
| --- | --- | --- |
| `dry-run` | Detección, creación del incidente, decisión y despacho | Las acciones quedan como `simulated`; no bloquea IP ni cuenta |
| `live` | El mismo flujo más la aplicación real del control y su rollback | Aplica controles temporales y comprueba su restauración |

---

## Prueba supervisada con controles reales

Esta sección es opcional para una comprobación rápida, pero permite demostrar
que los controles no solo se simulan. Debe ejecutarse únicamente dentro de la
red `10.20.0.0/24` y con acceso a las consolas de Ubuntu y Kali.

Primero prepare la verificación y confirme la salud:

```bash
make eval-deploy-live-verification
make eval-preflight \
  KALI_SSH=socadmin@10.20.0.30 \
  WINDOWS_SSH=socadmin@10.20.0.20
make soar-enable-live CONFIRM=live
make soar-health
```

Para evitar errores al repetir los destinos SSH, puede definirlos únicamente en
la sesión actual de la terminal. No es necesario guardarlos en `.env`:

```bash
export KALI_SSH_TARGET='socadmin@10.20.0.30'
export WINDOWS_SSH_TARGET='socadmin@10.20.0.20'
```

En los comandos siguientes puede sustituir los valores completos por
`KALI_SSH="$KALI_SSH_TARGET"` o `WINDOWS_SSH="$WINDOWS_SSH_TARGET"`.

Desde Kali, compruebe primero que la aplicación está disponible:

```bash
curl --noproxy '*' -o /dev/null -s \
  -w '%{http_code}\n' \
  http://10.20.0.10:8080/auth/login
```

El resultado esperado antes de aprobar la respuesta es `200`.

Luego, ejecute SCN-002 de nuevo en Ubuntu:

```bash
make eval-run \
  SCENARIO=SCN-002 \
  KALI_SSH=socadmin@10.20.0.30 \
  CONFIRM=live
```

La ejecución debe terminar en `PASS_PENDING_DECISION`. En este momento todavía no existe ningún bloqueo real.

Copie el `run_id` y apruebe la respuesta:

```bash
make eval-decide \
  RUN_ID=SF-EVAL-SCN-002-FECHA-Y-CODIGO-MOSTRADOS \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Prueba supervisada del bloqueo real y su restauración' \
  KALI_SSH=socadmin@10.20.0.30 \
  CONFIRM=live
```
Este escenario nos pedirá 3 veces la contraseña de Kali. Cuando solicite la contraseña la primera vez, se puede observar que la conexión a la app nos devuelve código HTTP 200. 
Tras colocar por segunda vez la contraseña, observaremos que el control fue aplicado, devolviéndonos un código HTTP 403. Una vez se cumple un TTL o luego de ingresar la contraseña
por tercera vez, veremos que el control fue revertido y ahora obtenemos un código HTTP 200 de nuevo.

La intervención humana consiste en aprobar la respuesta. Después de la
aprobación, la herramienta comprueba automáticamente estas tres fases:

1. antes del control, Kali recibe HTTP `200`;
2. mientras el bloqueo está activo, Kali recibe HTTP `403`;
3. después del rollback, Kali vuelve a recibir HTTP `200`.

La salida final debe mostrar:

- `status: PASS`;
- `response_mode: live`;
- acciones `rolled_back`;
- `live_control_verification.status: PASS`;
- validaciones `live_control_effect` y `rollback_restoration`.

Devuelva inmediatamente el sistema al modo seguro:

```bash
make soar-disable-live
make soar-health
```

El modo esperado al terminar es `response_mode=dry-run`.

---

## Campaña completa de evaluación

| Escenario | Fuente | Regla | Comprobación principal |
| --- | --- | ---: | --- |
| SCN-001 | Kali | 110100 | Ruta Suricata–Wazuh–SOAR |
| SCN-002 | Kali | 110011 | Cinco fallos correlacionados y aprobación |
| SCN-003 | Kali | 110120 | Ruta sensible inexistente y rechazo justificado |
| SCN-004 | Kali | 110130 | Indicador SQLi inerte y bloqueo propuesto |
| SCN-005 | Aplicación | 110020 | Ajuste de inventario compensado y usuario protegido |
| SCN-006 | Aplicación | 110030 | Control de calidad y `quality_guard` |
| SCN-007 | Ubuntu | 110210 | FIM de configuración de calidad |
| SCN-008 | Windows | 110211 | FIM WhoData de configuración de calidad |

Liste el catálogo:

```bash
make eval-list
```

Ejecute SCN-001 a SCN-004 con `KALI_SSH`, SCN-005 y SCN-006 desde Ubuntu,
SCN-007 con permisos `sudo` cuando se soliciten y SCN-008 con `WINDOWS_SSH`:

```bash
make eval-run SCENARIO=SCN-001 KALI_SSH=socadmin@10.20.0.30
make eval-run SCENARIO=SCN-002 KALI_SSH=socadmin@10.20.0.30
make eval-run SCENARIO=SCN-003 KALI_SSH=socadmin@10.20.0.30
make eval-run SCENARIO=SCN-004 KALI_SSH=socadmin@10.20.0.30
make eval-run SCENARIO=SCN-005
make eval-run SCENARIO=SCN-006
make eval-run SCENARIO=SCN-007
make eval-run SCENARIO=SCN-008 WINDOWS_SSH=socadmin@10.20.0.20
```

Cuando un escenario devuelva `PASS_PENDING_DECISION`, use su `run_id` exacto
con `make eval-decide`. Una decisión puede ser `approve` o `reject`; lo
importante es que corresponda al análisis y que el motivo quede escrito.

```bash
make eval-decide \
  RUN_ID=SF-EVAL-SCN-006-FECHA-Y-CODIGO-MOSTRADOS \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Decisión documentada para el escenario evaluado'
```

SCN-007 puede solicitar la contraseña de `sudo` la primera vez que modifica
el archivo vigilado en Ubuntu. Para evitar que la solicitud interrumpa la
medición, valide las credenciales inmediatamente antes de ejecutarlo:

```bash
sudo -v
make eval-run SCENARIO=SCN-007
```

En SCN-008, el cliente SSH puede mostrar una advertencia informativa sobre el
intercambio de claves poscuántico. Esa advertencia no implica por sí sola que
la prueba haya fallado. Si aparece un error real de PowerShell, Sysmon o
`Get-WinEvent`, siga la comprobación específica de
[SCN-008 en Windows](#scn-008-falla-al-consultar-sysmon-o-whodata) y repita
únicamente ese escenario.

Al terminar:

```bash
make eval-summary
```

Una campaña completa debe mostrar:

- ocho escenarios cubiertos;
- cobertura de `100.0` por ciento;
- `fail_count: 0`;
- `pending_decision_count: 0`;
- `invalid_timing_count: 0`.

Cada ejecución crea una carpeta local
`evaluation/results/runs/SF-EVAL-SCN-.../` con los datos que permiten seguir la
prueba de principio a fin:

- definición del escenario;
- hora exacta de inicio;
- alerta Wazuh encontrada;
- incidente y acciones SOAR;
- resultado y métricas;
- comprobación del control y rollback cuando se usa el modo `live`.

Los archivos JSON relacionan el mismo `run_id`, la alerta Wazuh y el incidente SOAR.

Los resultados de la evaluación ya validada están en
[`evidence/EVAL-001/summary.md`](evidence/EVAL-001/summary.md). La explicación
detallada de cada escenario se encuentra en
[`evaluation/README.md`](evaluation/README.md).

---

## Por qué se sincronizan los relojes

La detección pasa por varias máquinas. Kali registra cuándo inició la prueba,
Wazuh registra cuándo lo detectó y SOAR registra cuándo lo recibió y respondió.
Si cada equipo usa una hora distinta, una resta entre esas marcas produce una
métrica incorrecta.

Por eso `make eval-preflight` exige menos de un segundo de diferencia. La zona
horaria visible puede ser distinta; lo importante es que todos representen el
mismo instante en UTC.

---

## Encender, apagar y revisar el sistema

### Encender después de reiniciar las VMs

Encienda primero Ubuntu, luego Windows y Kali. En Ubuntu:

```bash
cd ~/sanolifood-soc
make soc-up
make soc-health
```

Si Windows o Kali no son necesarios, pueden permanecer apagados. En ese caso,
compruebe los servicios centrales por separado porque `make soc-health`
informará que faltan los endpoints:

```bash
make health
make wazuh-health
make suricata-health
make soar-health
```

### Ver estado

```bash
docker ps
make ps
make wazuh-ps
make suricata-ps
make soar-ps
```

### Ver logs

```bash
make logs
make wazuh-logs
make suricata-logs
make soar-logs
```

Los comandos de logs permanecen abiertos; salga con `Ctrl+C`.

### Apagar de forma ordenada

```bash
make soar-disable-live
make soar-down
make wazuh-down
make suricata-down
make down
```

Estos comandos detienen los contenedores sin borrar los volúmenes.

---

## Resolución de problemas

### Reinicio completo del laboratorio

Antes de reiniciar desde cero, corrija primero `.env` y repita `make soc-up`;
Docker Compose puede reconciliar la configuración sin eliminar los datos. Si
realmente necesita descartar el laboratorio, la opción más segura y
reproducible es restaurar una instantánea limpia de Ubuntu o volver a importar
la VM.

> [!WARNING]
> No utilice `docker system prune`, eliminaciones globales de volúmenes ni
> comandos con destinos ambiguos. El repositorio contiene varios proyectos
> Compose y una limpieza general puede borrar evidencias y otros entornos del
> host.

Antes de restaurar la instantánea, detenga de forma ordenada los componentes:

```bash
make soar-disable-live
make soar-down
make wazuh-down
make suricata-down
make down
```

Estos comandos detienen el entorno, pero no borran los volúmenes. Conserve una
copia de cualquier evidencia que no esté versionada antes de reemplazar la VM.

### Docker responde `permission denied`

```bash
groups
sudo usermod -aG docker "$USER"
```

Cierre la sesión y vuelva a entrar. Después pruebe `docker info`.

### OpenSSH instalado con Chocolatey no inicia `sshd`

Al instalar OpenSSH mediante Chocolatey, es posible que el servicio `sshd` pierda su configuración, incluso luego de haber sido configurado correctamente. Puede ocurrir en particular luego de un reinicio o una actualización del sistema.

En tal caso, primero se debe comprobar si el paquete sigue instalado utilizando el comando `choco list --local-only openssh`.

Si se muestra una entrada correspondiente a `openssh`, significa que el paquete sigue instalado. En caso contrario, se debe reinstalar utilizando `choco install openssh -params "'/SSHServerFeature /SSHAgentFeature'" -y`.

Luego configure el servicio `sshd` como se indica a continuación:

```powershell
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Get-Service sshd
```

Si esto no tiene efecto, debido a que el servicio `sshd` no se reconoce, puede que el registro del servicio se haya perdido. Se puede recrear utilizando el siguiente comando en PowerShell como administrador:

```powershell
& "C:\Program Files\OpenSSH-Win64\install-sshd.ps1"
```

Después repita la configuración del servicio indicada anteriormente. El
comando supone que OpenSSH se encuentra en
`C:\Program Files\OpenSSH-Win64`; compruebe y adapte la ruta si Chocolatey lo
instaló en otra ubicación.

### Wazuh indexer no inicia

```bash
sysctl vm.max_map_count
make wazuh-ps
make wazuh-logs
```

Si el valor es menor que `262144`, repita la configuración de `sysctl` de esta
guía. Compruebe también que Ubuntu tenga al menos 8 GiB de RAM disponibles.

### Nginx aparece `unhealthy`

```bash
make ps
docker compose logs --tail=150 app nginx postgres
curl -v http://127.0.0.1:8080/health/ready
```

Espere a que PostgreSQL y la aplicación estén saludables. Si el puerto 8080 ya
está ocupado, identifique el proceso con `sudo ss -ltnp | grep ':8080'`.

### Suricata usa la interfaz equivocada

```bash
ip -br address
cat suricata/runtime/.env
SURICATA_INTERFACE_OVERRIDE=enp0s8 \
SURICATA_HOME_NET_OVERRIDE=10.20.0.0/24 \
make suricata-up
make suricata-health
```

No use la interfaz de administración para la campaña.

### Un agente Wazuh no aparece activo

En Ubuntu:

```bash
sudo systemctl status wazuh-agent --no-pager
sudo journalctl -u wazuh-agent -n 100 --no-pager
make endpoint-health
```

En Windows, PowerShell como administrador:

```powershell
Get-Service WazuhSvc, Sysmon64, sshd
Test-NetConnection 10.20.0.10 -Port 1514
Test-NetConnection 10.20.0.10 -Port 1515
```

Compruebe que la IP interna sea correcta y que no exista una puerta de enlace
en el segundo adaptador.

### `eval-preflight` informa diferencia de hora

En Ubuntu:

```bash
chronyc tracking
sudo chronyc clients
```

En Kali:

```bash
timedatectl status
timedatectl timesync-status
```

En Windows:

```powershell
w32tm /query /source
w32tm /query /status
w32tm /resync /rediscover
```

Confirme que Kali y Windows estén usando `10.20.0.10` y espere unos segundos
antes de repetir el preflight.

### SCN-008 falla al consultar Sysmon o WhoData

La advertencia de OpenSSH sobre la ausencia de un intercambio de claves
poscuántico es informativa y no suele ser la causa del fallo. Primero confirme
en PowerShell como administrador que los servicios y el registro de Sysmon
estén disponibles:

```powershell
Get-Service WazuhSvc, Sysmon64, sshd
Get-WinEvent -ListLog 'Microsoft-Windows-Sysmon/Operational'
Get-WinEvent -LogName 'Microsoft-Windows-Sysmon/Operational' -MaxEvents 5
```

Ejecute después la validación local del endpoint para separar un problema de
Windows de uno relacionado con SSH:

```powershell
& "$env:USERPROFILE\SanoliFood-Endpoint\Test-SanoliFoodEndpoint.ps1"
```

Si la validación local termina correctamente, vuelva a Ubuntu y repita solo
SCN-008. Los mensajes `CLIXML` o `Preparing modules for first use` pueden ser
salida serializada de PowerShell; el dato decisivo es que el comando termine
sin una excepción de `Get-WinEvent` y que la ejecución produzca su `run_id`.

### n8n está healthy pero no recibe alertas

```bash
make soar-health
make soar-install-workflows
make wazuh-reload-rules
make soar-logs
make wazuh-logs
```

En n8n confirme que los cinco workflows estén publicados. El reenvío Wazuh se
mantiene deshabilitado si la publicación no termina correctamente.

### Una acción queda en `failed`

```bash
make soar-show INCIDENT_ID=UUID
make soar-logs
make soar-retry ACTION_ID=UUID ANALYST=nombre.apellido
```

No active el modo `live` para ocultar un error. Primero resuelva la causa y vuelva a
validar en `dry-run`.

### Se interrumpió una prueba en modo live

```bash
make soar-disable-live
make soar-incidents
make soar-show INCIDENT_ID=UUID
make soar-rollback ACTION_ID=UUID ANALYST=nombre.apellido
make soar-health
```

Los controles tienen TTL y rollback, pero conviene verificar de forma explícita
que la aplicación haya vuelto al estado esperado.

---

## Puertos publicados

| Puerto | Servicio | Exposición esperada |
| ---: | --- | --- |
| 8080/TCP | Aplicación mediante Nginx | Red de administración y laboratorio |
| 8443/TCP | Wazuh Dashboard | Red de administración |
| 1514/TCP | Eventos de agentes | Solo `10.20.0.0/24` |
| 1515/TCP | Registro de agentes | Solo `10.20.0.0/24` |
| 514/UDP | Entrada syslog | Solo `10.20.0.0/24` |
| 5678/TCP | n8n | Solo `127.0.0.1`; acceso por túnel SSH |
| 5680/TCP | Controlador SOAR | Solo `127.0.0.1` |

El indexer y las bases de datos no se publican directamente en el host.

---

## Datos que no deben compartirse

- `.env`;
- `wazuh/runtime/.env`;
- `suricata/runtime/.env`;
- `n8n/runtime/.env` y `n8n/runtime/secrets/`;
- respaldos de PostgreSQL;
- cookies o credenciales de n8n;
- claves privadas y tokens internos.

---

## Documentación incluida

- [`n8n/README.md`](n8n/README.md): funcionamiento y operación SOAR.
- [`evaluation/README.md`](evaluation/README.md): campaña y métricas.
- [`scenarios/kali/README.md`](scenarios/kali/README.md): pruebas controladas desde Kali.
- [`scenarios/business/README.md`](scenarios/business/README.md): escenarios empresariales.
- [`CHANGELOG.md`](CHANGELOG.md): cambios entre versiones.
- [`docs/adr/`](docs/adr/): decisiones técnicas del diseño.

---

## Referencias oficiales

- [Instalación de Docker Engine en Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Uso de Docker sin sudo](https://docs.docker.com/engine/install/linux-postinstall/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Despliegue de Wazuh con Docker](https://documentation.wazuh.com/current/deployment-options/docker/index.html)
- [Navegación del Wazuh Dashboard](https://documentation.wazuh.com/current/user-manual/wazuh-dashboard/navigating-the-wazuh-dashboard.html)
- [File Integrity Monitoring de Wazuh](https://documentation.wazuh.com/current/user-manual/capabilities/file-integrity/index.html)
- [Documentación de Suricata](https://docs.suricata.io/)
- [Documentación de n8n](https://docs.n8n.io/)
- [Kali en VirtualBox](https://www.kali.org/docs/virtualization/import-premade-virtualbox/)
- [Redes de VirtualBox](https://www.virtualbox.org/manual/topics/networkingdetails.html)
- [OpenSSH Server en Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Herramientas del servicio de hora de Windows](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)
- [MITRE ATT&CK](https://attack.mitre.org/)

---

## Resultado validado incluido

La campaña validada almacenada en `evidence/EVAL-001/` registra:

- 8 de 8 escenarios cubiertos;
- 100 % de cobertura;
- 10 ejecuciones aprobadas;
- 0 fallos;
- 0 decisiones pendientes;
- 0 cronologías inválidas;
- 2 ejecuciones verificadas en modo real;
- 3 controles reales restaurados.

Estos resultados permiten revisar una ejecución ya completada. Las secciones
anteriores permiten repetirla desde una instalación nueva.
