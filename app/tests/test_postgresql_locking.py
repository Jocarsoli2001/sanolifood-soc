from sqlalchemy.dialects import postgresql

from sanolifood.services.operations import (
    _ingredient_for_update_query,
    _production_lot_for_update_query,
)


def postgresql_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_ingredient_lock_targets_only_ingredient_table() -> None:
    sql = postgresql_sql(_ingredient_for_update_query(1))

    assert "JOIN suppliers" not in sql
    assert sql.strip().endswith("FOR UPDATE OF ingredients")


def test_production_lot_lock_targets_only_lot_table() -> None:
    sql = postgresql_sql(_production_lot_for_update_query(1))

    assert " JOIN " not in sql
    assert sql.strip().endswith("FOR UPDATE OF production_lots")
