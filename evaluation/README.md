# Evaluación final v0.8.0

La campaña mide ocho recorridos atribuibles a una ejecución concreta. Cada
identificador `SF-EVAL-SCN-*` debe aparecer en el estímulo y en la alerta Wazuh;
el incidente se enlaza después mediante `source_alert_id`. Esto impide que una
alerta histórica produzca un falso aprobado.

El inicio de MTTD se toma del recibo emitido justo antes del estímulo. No incluye
el tiempo utilizado para escribir una contraseña SSH, comprobar salud o iniciar
sesión en la aplicación.

La campaña final exige relojes sincronizados. Ubuntu sirve NTP mediante Chrony
a `10.20.0.0/24`; Kali y Windows deben usar `10.20.0.10` como fuente. El
preflight comprueba `Leap status: Normal`, la fuente horaria de Windows y un
desfase máximo de un segundo para ambos equipos remotos. Un intervalo negativo
se considera cronología inválida: nunca se convierte artificialmente en cero ni
se incorpora a la cobertura o a las métricas agregadas.

## Fuentes y escenarios

| Escenario | Fuente | Regla | Resultado esperado |
|---|---|---:|---|
| SCN-001 | Kali | 110100 | NDR y evidencia automática |
| SCN-002 | Kali | 110011 | Correlación de cinco fallos y decisión |
| SCN-003 | Kali | 110120 | Ruta sensible inexistente y decisión |
| SCN-004 | Kali | 110130 | Indicador inerte, decisión y contención simulada |
| SCN-005 | Aplicación | 110020 | Ajuste compensado y usuario protegido |
| SCN-006 | Aplicación | 110030 | Desviación de calidad y decisión |
| SCN-007 | Ubuntu | 110210 | FIM con identificador y decisión |
| SCN-008 | Windows | 110211 | WhoData con identificador y decisión |

Kali se limita a `10.20.0.30 -> 10.20.0.10:8080`. El ejecutor no acepta otro
objetivo ni herramientas genéricas y aplica un presupuesto máximo de
solicitudes. Las pruebas se ejecutan primero con SOAR en `dry-run`.

## Secuencia operativa

```bash
make upgrade-0.8
make eval-list
make eval-preflight \
  KALI_SSH=usuario@10.20.0.30 \
  WINDOWS_SSH=usuario@10.20.0.20
make eval-run SCENARIO=SCN-001 KALI_SSH=usuario@10.20.0.30
```

Cuando una ejecución indique `PASS_PENDING_DECISION`, se usa exactamente el
`RUN_ID` mostrado:

```bash
make eval-decide \
  RUN_ID=SF-EVAL-SCN-... \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Decisión documentada para la ejecución controlada'
```

Los escenarios de Ubuntu y Windows requieren respectivamente `sudo` y el
destino `WINDOWS_SSH=usuario@10.20.0.20`. Tras actualizar el repositorio debe
volver a prepararse el script Windows con `make endpoint-stage-windows`.

Finalmente:

```bash
make eval-summary
make evidence-evaluation
```

Las ejecuciones usadas para depurar instalación, reglas o sincronización son
pilotos. Deben conservarse fuera de `evaluation/results/runs/` antes de iniciar
una campaña final limpia; solo resultados `PASS` con `timing_integrity=valid`
aportan cobertura y muestras estadísticas.

`EVAL-001` exige al menos una ejecución supervisada en modo real que demuestre
las tres fases del control: operación permitida antes de responder, operación
denegada mientras el control está activo y operación permitida nuevamente tras
el rollback. El evaluador guarda esta secuencia en
`live-control-verification.json`; un control que solo cambie de estado en la
base de datos no supera la prueba.

Antes de activar live debe desplegarse el endpoint de comprobación de solo
lectura y ejecutarse la regresión completa:

```bash
make eval-deploy-live-verification
make eval-preflight \
  KALI_SSH=usuario@10.20.0.30 \
  WINDOWS_SSH=usuario@10.20.0.20
```

En un escenario con `app_ip_block`, `eval-decide` exige nuevamente
`KALI_SSH`. Kali prueba una ruta real y debe observar HTTP `200 -> 403 -> 200`.
Los guards de cuenta y calidad se evalúan mediante el endpoint interno
autenticado que comparte la misma consulta de controles que la aplicación, sin
crear intentos de acceso ni cambiar lotes. El rollback se ejecuta en una
cláusula de limpieza aunque falle la comprobación activa.

```bash
make soar-enable-live CONFIRM=live
make eval-run \
  SCENARIO=SCN-002 \
  KALI_SSH=usuario@10.20.0.30 \
  CONFIRM=live
make eval-decide \
  RUN_ID=SF-EVAL-SCN-... \
  DECISION=approve \
  ANALYST=nombre.apellido \
  REASON='Validación supervisada del efecto y rollback de los controles' \
  KALI_SSH=usuario@10.20.0.30 \
  CONFIRM=live
make soar-disable-live
```

`evaluation/results/` es runtime ignorado por Git. `evidence/EVAL-001` contiene
la selección textual revisable para el hito.
