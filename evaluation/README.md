# Evaluación final v0.8.0

La campaña mide ocho recorridos atribuibles a una ejecución concreta. Cada
identificador `SF-EVAL-SCN-*` debe aparecer en el estímulo y en la alerta Wazuh;
el incidente se enlaza después mediante `source_alert_id`. Esto impide que una
alerta histórica produzca un falso aprobado.

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
make eval-preflight KALI_SSH=usuario@10.20.0.30
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

`EVAL-001` exige al menos una ejecución supervisada en modo real cuyo control
reversible haya quedado en `rolled_back`. Para esa única repetición se usan
`make soar-enable-live CONFIRM=live`, `CONFIRM=live` tanto en `eval-run` como en
`eval-decide`, y finalmente `make soar-disable-live`.

`evaluation/results/` es runtime ignorado por Git. `evidence/EVAL-001` contiene
la selección textual revisable para el hito.
