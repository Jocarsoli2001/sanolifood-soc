# ADR-009: Campaña de evaluación atribuible y acotada

## Estado

Aceptada para v0.8.0.

## Contexto

Las validaciones anteriores demostraban cada integración, pero algunas podían
encontrar una alerta histórica con el mismo identificador de regla. La
evaluación final necesita medir una ejecución concreta, separar tiempos de
detección y respuesta, y preservar el carácter seguro del laboratorio.

## Decisión

Se define un catálogo versionado de ocho escenarios. Cada ejecución genera un
identificador único que debe estar presente en el estímulo y en la alerta
Wazuh. El incidente n8n se relaciona mediante el identificador nativo de esa
alerta. Kali usa una dirección fija y solo puede enviar cuatro estímulos HTTP
predeterminados al único destino permitido. La aplicación produce dos eventos
de negocio y los endpoints producen dos cambios FIM sintéticos.

Los resultados se conservan fuera de Git durante la campaña. El paquete
`EVAL-001` incorpora únicamente resultados, alertas, casos, estados y hashes
revisados. Las métricas de la campaña no mezclan los incidentes de desarrollo
almacenados anteriormente en PostgreSQL SOAR.

## Salvaguardas

- Red interna `10.20.0.0/24` sin objetivo configurable.
- Presupuesto de solicitudes y tiempo máximo por ejecución.
- Rutas web inexistentes, usuario ficticio y cadena SQL inerte.
- Compensación exacta del ajuste de inventario.
- `dry-run` por defecto y confirmación explícita para modo real.
- Aprobación humana y rollback inmediato de toda acción real reversible.
- Correlación por marcador y marca temporal, no solo por ID de regla.

## Consecuencias

La evaluación requiere preparar Kali y volver a distribuir el script Windows.
A cambio, cada resultado puede defenderse como un recorrido completo y
repetible desde el estímulo hasta la evidencia y la respuesta.
