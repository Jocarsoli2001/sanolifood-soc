import re
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.database.session import engine
from sanolifood.models import (
    AuditEvent,
    Ingredient,
    InventoryMovement,
    Product,
    ProductionLot,
    QualityCheck,
    Recipe,
    RecipeItem,
    Supplier,
)


def csrf_from(response_text: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response_text)
    assert match
    return match.group(1)


def login(client: TestClient, username: str, password: str = "SanoliFood!2026") -> None:
    page = client.get("/auth/login")
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password, "csrf_token": csrf_from(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def seed_catalog(*, stock: Decimal = Decimal("200"), reorder: Decimal = Decimal("40")) -> dict[str, int]:
    with Session(engine) as db:
        supplier = Supplier(
            code="SUP-TEST",
            name="Proveedor de Pruebas",
            country="Guatemala",
            risk_level="low",
        )
        db.add(supplier)
        db.flush()
        ingredient = Ingredient(
            sku="ING-TEST-001",
            name="Ingrediente de pruebas",
            category="Validación",
            unit="kg",
            reorder_level=reorder,
            current_stock=stock,
            supplier_id=supplier.id,
        )
        product = Product(
            sku="PRD-TEST-001",
            name="Producto de pruebas",
            unit="unidad",
            shelf_life_days=90,
        )
        db.add_all([ingredient, product])
        db.flush()
        recipe = Recipe(
            product_id=product.id,
            version=1,
            yield_quantity=Decimal("100"),
            status="approved",
        )
        db.add(recipe)
        db.flush()
        db.add(RecipeItem(recipe_id=recipe.id, ingredient_id=ingredient.id, quantity=Decimal("25")))
        db.commit()
        return {
            "supplier_id": supplier.id,
            "ingredient_id": ingredient.id,
            "product_id": product.id,
            "recipe_id": recipe.id,
        }


def create_lot(
    *, product_id: int, recipe_id: int, status: str = "planned", code: str = "SF26-TST-0001"
) -> int:
    with Session(engine) as db:
        lot = ProductionLot(
            lot_code=code,
            product_id=product_id,
            recipe_id=recipe_id,
            planned_quantity=Decimal("100"),
            status=status,
            scheduled_at=datetime.now(timezone.utc),
        )
        db.add(lot)
        db.commit()
        return lot.id


def test_business_pages_require_login(client: TestClient) -> None:
    for path in ("/inventory", "/production", "/quality"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"


def test_seeded_catalog_renders_all_operational_pages(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    identifiers = seed_catalog()
    create_lot(product_id=identifiers["product_id"], recipe_id=identifiers["recipe_id"], status="in_progress")
    login(client, "admin.sanolifood")

    inventory = client.get("/inventory")
    production = client.get("/production")
    quality = client.get("/quality")
    assert inventory.status_code == production.status_code == quality.status_code == 200
    assert "Ingrediente de pruebas" in inventory.text
    assert "Producto de pruebas" in production.text
    assert "SF26-TST-0001" in quality.text


def test_warehouse_records_atomic_consumption_and_audit(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="warehouse.operator", role="warehouse", full_name="Operador Almacén")
    identifiers = seed_catalog()
    login(client, "warehouse.operator")
    page = client.get("/inventory")
    response = client.post(
        "/inventory/movements",
        data={
            "ingredient_id": identifiers["ingredient_id"],
            "movement_type": "consumption",
            "quantity": "25",
            "reference": "LOT-SF-TEST",
            "reason": "Consumo de lote controlado",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        ingredient = db.get(Ingredient, identifiers["ingredient_id"])
        movement = db.scalar(select(InventoryMovement).order_by(InventoryMovement.id.desc()))
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "inventory.movement.recorded"))
        assert ingredient is not None and ingredient.current_stock == Decimal("175.000")
        assert movement is not None and movement.quantity_delta == Decimal("-25.000")
        assert event is not None and event.actor_username == "warehouse.operator"


def test_inventory_rejects_negative_balance_without_partial_write(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="warehouse.operator", role="warehouse", full_name="Operador Almacén")
    identifiers = seed_catalog(stock=Decimal("10"))
    login(client, "warehouse.operator")
    page = client.get("/inventory")
    response = client.post(
        "/inventory/movements",
        data={
            "ingredient_id": identifiers["ingredient_id"],
            "movement_type": "consumption",
            "quantity": "25",
            "reference": "LOT-OVERDRAW",
            "reason": "Prueba de invariante",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 422
    assert "existencias negativas" in response.text
    with Session(engine) as db:
        ingredient = db.get(Ingredient, identifiers["ingredient_id"])
        count = db.scalar(select(func.count()).select_from(InventoryMovement))
        assert ingredient is not None and ingredient.current_stock == Decimal("10.000")
        assert count == 0


def test_high_value_adjustment_emits_specific_detection_event(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    identifiers = seed_catalog()
    login(client, "admin.sanolifood")
    page = client.get("/inventory")
    response = client.post(
        "/inventory/movements",
        data={
            "ingredient_id": identifiers["ingredient_id"],
            "movement_type": "adjustment",
            "quantity": "150",
            "reference": "ADJ-TEST-150",
            "reason": "Escenario de detección",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "inventory.adjustment.high_value"))
        assert event is not None
        assert event.details["quantity_delta"] == "150.000"


def test_production_user_creates_and_advances_lot(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="production.operator", role="production", full_name="Operador Producción")
    identifiers = seed_catalog()
    login(client, "production.operator")
    page = client.get("/production")
    response = client.post(
        "/production/lots",
        data={
            "lot_code": "SF26-TST-0002",
            "product_id": identifiers["product_id"],
            "planned_quantity": "125",
            "scheduled_at": "2026-08-18T08:30",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/production")
    with Session(engine) as db:
        lot = db.scalar(select(ProductionLot).where(ProductionLot.lot_code == "SF26-TST-0002"))
        assert lot is not None
        lot_id = lot.id
    response = client.post(
        f"/production/lots/{lot_id}/transition",
        data={"target_status": "in_progress", "csrf_token": csrf_from(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "production.lot.status_changed")
        )
        consumption_event = db.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "production.lot.materials_consumed")
        )
        ingredient = db.get(Ingredient, identifiers["ingredient_id"])
        assert lot is not None and lot.status == "in_progress" and lot.started_at is not None
        assert event is not None
        assert consumption_event is not None and consumption_event.details["movement_count"] == 1
        assert ingredient is not None and ingredient.current_stock == Decimal("168.750")


def test_lot_start_rolls_back_when_recipe_material_is_insufficient(
    client: TestClient, user_factory: Callable
) -> None:
    user_factory(username="production.operator", role="production", full_name="Operador Producción")
    identifiers = seed_catalog(stock=Decimal("10"))
    lot_id = create_lot(
        product_id=identifiers["product_id"],
        recipe_id=identifiers["recipe_id"],
        status="planned",
        code="SF26-TST-LOW1",
    )
    login(client, "production.operator")
    page = client.get("/production")
    response = client.post(
        f"/production/lots/{lot_id}/transition",
        data={"target_status": "in_progress", "csrf_token": csrf_from(page.text)},
    )
    assert response.status_code == 422
    assert "existencias negativas" in response.text
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        ingredient = db.get(Ingredient, identifiers["ingredient_id"])
        movements = db.scalar(select(func.count()).select_from(InventoryMovement))
        assert lot is not None and lot.status == "planned"
        assert ingredient is not None and ingredient.current_stock == Decimal("10.000")
        assert movements == 0


def test_failed_quality_check_automatically_holds_lot(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    identifiers = seed_catalog()
    lot_id = create_lot(product_id=identifiers["product_id"], recipe_id=identifiers["recipe_id"], status="in_progress")
    login(client, "quality.operator")
    page = client.get("/quality")
    response = client.post(
        "/quality/checks",
        data={
            "lot_id": lot_id,
            "check_type": "pH",
            "measured_value": "5.2",
            "unit": "pH",
            "min_value": "4.0",
            "max_value": "4.6",
            "notes": "Desviación reproducible",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        check = db.scalar(select(QualityCheck).where(QualityCheck.production_lot_id == lot_id))
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "quality.check.failed"))
        assert lot is not None and lot.status == "quality_hold"
        assert check is not None and check.result == "fail"
        assert event is not None and event.outcome == "failure"


def test_release_is_blocked_while_failed_check_exists(client: TestClient, user_factory: Callable) -> None:
    user = user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    identifiers = seed_catalog()
    lot_id = create_lot(product_id=identifiers["product_id"], recipe_id=identifiers["recipe_id"], status="quality_hold")
    with Session(engine) as db:
        db.add(
            QualityCheck(
                production_lot_id=lot_id,
                check_type="pH",
                measured_value=Decimal("5.2"),
                unit="pH",
                min_value=Decimal("4.0"),
                max_value=Decimal("4.6"),
                result="fail",
                inspected_by_user_id=user.id,
            )
        )
        db.commit()
    login(client, "quality.operator")
    page = client.get("/quality")
    response = client.post(
        f"/quality/lots/{lot_id}/decision",
        data={"decision": "released", "csrf_token": csrf_from(page.text)},
    )
    assert response.status_code == 422
    assert "controles fallidos" in response.text
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        assert lot is not None and lot.status == "quality_hold"


def test_passed_check_allows_quality_release(client: TestClient, user_factory: Callable) -> None:
    user = user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    identifiers = seed_catalog()
    lot_id = create_lot(product_id=identifiers["product_id"], recipe_id=identifiers["recipe_id"], status="quality_hold")
    with Session(engine) as db:
        db.add(
            QualityCheck(
                production_lot_id=lot_id,
                check_type="pH",
                measured_value=Decimal("4.3"),
                unit="pH",
                min_value=Decimal("4.0"),
                max_value=Decimal("4.6"),
                result="pass",
                inspected_by_user_id=user.id,
            )
        )
        db.commit()
    login(client, "quality.operator")
    page = client.get("/quality")
    response = client.post(
        f"/quality/lots/{lot_id}/decision",
        data={"decision": "released", "csrf_token": csrf_from(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "quality.lot.released"))
        assert lot is not None and lot.status == "released" and lot.completed_at is not None
        assert event is not None


def test_approved_soar_guard_temporarily_suspends_quality_release(
    client: TestClient,
    user_factory: Callable,
) -> None:
    user = user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    identifiers = seed_catalog()
    lot_id = create_lot(
        product_id=identifiers["product_id"],
        recipe_id=identifiers["recipe_id"],
        status="quality_hold",
    )
    with Session(engine) as db:
        db.add(
            QualityCheck(
                production_lot_id=lot_id,
                check_type="pH",
                measured_value=Decimal("4.3"),
                unit="pH",
                min_value=Decimal("4.0"),
                max_value=Decimal("4.6"),
                result="pass",
                inspected_by_user_id=user.id,
            )
        )
        db.commit()

    control = client.post(
        "/internal/soar/controls",
        headers={
            "Authorization": (
                "Bearer test-soar-internal-token-with-more-than-thirty-two-characters"
            )
        },
        json={
            "action_id": "44444444-4444-4444-8444-444444444444",
            "incident_id": "55555555-5555-4555-8555-555555555555",
            "control_type": "quality_guard",
            "target": "quality-release",
            "ttl_seconds": 600,
            "reason": "Suspensión temporal aprobada para investigar integridad de configuración.",
        },
    )
    assert control.status_code == 200

    login(client, "quality.operator")
    page = client.get("/quality")
    response = client.post(
        f"/quality/lots/{lot_id}/decision",
        data={"decision": "released", "csrf_token": csrf_from(page.text)},
    )
    assert response.status_code == 422
    assert "suspendida temporalmente" in response.text
    with Session(engine) as db:
        lot = db.get(ProductionLot, lot_id)
        assert lot is not None and lot.status == "quality_hold"


def test_rbac_separates_warehouse_production_and_quality(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="warehouse.operator", role="warehouse", full_name="Operador Almacén")
    identifiers = seed_catalog()
    login(client, "warehouse.operator")
    page = client.get("/production")
    response = client.post(
        "/production/products",
        data={
            "sku": "PRD-NO-AUTH",
            "name": "Operación no autorizada",
            "description": "",
            "unit": "unidad",
            "shelf_life_days": 30,
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(Product.id).where(Product.sku == "PRD-NO-AUTH")) is None
        assert db.get(Product, identifiers["product_id"]) is not None
