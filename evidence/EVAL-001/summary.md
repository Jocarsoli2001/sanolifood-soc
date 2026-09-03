# Resumen de evaluación SanoliFood SOC

Generado: `2026-09-03T19:13:44.683266+00:00`

- Ejecuciones: 10
- Aprobadas: 10
- Pendientes de decisión: 0
- Fallidas: 0
- Aprobadas excluidas por cronología inválida: 0
- Escenarios completos: SCN-001, SCN-002, SCN-003, SCN-004, SCN-005, SCN-006, SCN-007, SCN-008
- Cobertura del catálogo: 100.0%
- Acciones reales revertidas: 3
- Ejecuciones live con efecto y restauración comprobados: 2

| Métrica | n | Media (s) | Mediana (s) | p95 (s) |
|---|---:|---:|---:|---:|
| stimulus_to_wazuh_seconds | 10 | 0.969 | 1.032 | 2.008 |
| wazuh_to_soar_seconds | 10 | 1.101 | 1.099 | 1.992 |
| soar_triage_seconds | 10 | 0.069 | 0.057 | 0.132 |
| end_to_end_triage_seconds | 10 | 2.139 | 2.264 | 3.512 |
| analyst_decision_seconds | 8 | 49.314 | 38.752 | 140.756 |
| decision_to_response_seconds | 7 | 0.053 | 0.056 | 0.065 |
| decision_to_containment_seconds | 2 | 0.055 | 0.055 | 0.057 |
| containment_to_rollback_seconds | 2 | 28.368 | 28.368 | 56.513 |
