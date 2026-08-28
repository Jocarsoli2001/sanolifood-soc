# ADR-008: plano SOAR durable con aprobación y rollback

- Estado: aceptada
- Fecha: 2026-08-26

## Contexto

El laboratorio necesita responder a múltiples familias de alertas sin convertir
n8n en la única fuente de verdad ni permitir que una detección ejecute por sí
sola una contención con impacto. Las ejecuciones de un orquestador pueden
reintentarse, interrumpirse o recibirse más de una vez; además, los bloqueos
temporales deben sobrevivir a un reinicio y poder auditarse.

## Decisión

n8n se utiliza como capa de orquestación. Un controlador FastAPI separado
mantiene incidentes, acciones, decisiones, errores y métricas en PostgreSQL. El
catálogo de playbooks se versiona y valida en tres puntos: integrador Wazuh,
workflow de triage y controlador.

Las acciones sin impacto, como conservar evidencia, pueden ser automáticas. Una
contención debe cumplir todas estas condiciones:

- aprobación humana autenticada y justificada;
- identificador idempotente estable;
- destino dentro de una allowlist y fuera de los activos protegidos;
- tiempo máximo de vida;
- operación de rollback;
- auditoría de intentos, resultado, actor y tiempos;
- modo `dry-run` como valor inicial.

Los controles empresariales se materializan en PostgreSQL y se aplican en los
puntos de decisión de la aplicación: entrada HTTP, autenticación y liberación de
lotes. El flujo programado de n8n solicita rollback al caducar cada acción.

## Consecuencias

La plataforma puede ejecutar varias respuestas por incidente y reanudar la
operación después de reinicios sin duplicarlas. El diseño requiere una base
adicional y un controlador pequeño, pero evita depender de variables internas
de workflows para el estado crítico. Añadir adaptadores futuros exige
implementar validación, ejecución, rollback y pruebas antes de incluirlos en el
catálogo.
