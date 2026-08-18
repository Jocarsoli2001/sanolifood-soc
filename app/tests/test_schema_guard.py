from sanolifood.database.session import engine
from sanolifood.schema_guard import REQUIRED_TABLES, missing_required_tables, schema_status


def test_schema_guard_accepts_complete_schema() -> None:
    assert missing_required_tables(set(REQUIRED_TABLES)) == set()


def test_schema_guard_reports_missing_tables() -> None:
    assert missing_required_tables({"alembic_version"}) == REQUIRED_TABLES - {"alembic_version"}


def test_schema_status_inspects_the_isolated_database() -> None:
    existing, missing = schema_status(engine)
    assert REQUIRED_TABLES - {"alembic_version"} <= existing
    assert missing == {"alembic_version"}
