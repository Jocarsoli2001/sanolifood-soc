import logging

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from sanolifood.core.config import get_settings
from sanolifood.core.logging import configure_logging
from sanolifood.database.session import engine


REQUIRED_TABLES = frozenset({"alembic_version", "platform_metadata", "users", "audit_events"})


def missing_required_tables(existing_tables: set[str]) -> set[str]:
    return set(REQUIRED_TABLES) - existing_tables


def schema_status(db_engine: Engine = engine) -> tuple[set[str], set[str]]:
    """Return existing and missing tables for startup and readiness checks."""
    existing_tables = set(inspect(db_engine).get_table_names())
    return existing_tables, missing_required_tables(existing_tables)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("sanolifood.schema")
    existing_tables, missing = schema_status(engine)
    if missing:
        logger.critical(
            "database_schema_incomplete",
            extra={
                "event_type": "database.schema.invalid",
                "missing_tables": sorted(missing),
                "existing_tables": sorted(existing_tables),
                "remediation": "Use the documented clean rebuild or restore a validated database backup.",
            },
        )
        raise SystemExit(78)
    logger.info(
        "database_schema_verified",
        extra={
            "event_type": "database.schema.verified",
            "required_tables": sorted(REQUIRED_TABLES),
        },
    )


if __name__ == "__main__":
    main()
