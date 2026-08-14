# ADR-001: Monolito modular para SanoliFood Operations

- Estado: aceptada
- Fecha: 2026-08-13

## Contexto

El laboratorio requiere una aplicación empresarial creíble, telemetría de negocio y despliegue
reproducible con recursos limitados. Una arquitectura de microservicios aumentaría el número de
componentes, secretos, redes y fallos sin aportar valor proporcional a las detecciones del TFM.

## Decisión

Se adopta un monolito modular FastAPI con separación por dominio, PostgreSQL transaccional,
Alembic, interfaz renderizada en servidor y Nginx como único punto expuesto.

## Consecuencias

- Menor coste operativo y de pruebas.
- Transacciones coherentes entre inventario, producción y calidad.
- Límites de módulo explícitos que permiten evolucionar sin concentrar toda la lógica en `main.py`.
- La aplicación puede generar eventos JSON consistentes con un único contexto de correlación.

