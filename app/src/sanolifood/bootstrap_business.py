import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from sanolifood.core.events import record_event
from sanolifood.core.logging import configure_logging
from sanolifood.database.session import SessionLocal
from sanolifood.models import (
    Ingredient,
    InventoryMovement,
    Product,
    ProductionLot,
    QualityCheck,
    Recipe,
    RecipeItem,
    Supplier,
    User,
    UserRole,
)


def main() -> None:
    configure_logging("INFO")
    logger = logging.getLogger("sanolifood.business.bootstrap")
    with SessionLocal() as db:
        if db.scalar(select(Supplier.id).limit(1)) is not None:
            logger.info("business_seed_exists", extra={"event_type": "business.seed.exists"})
            return

        admin = db.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1))
        suppliers = [
            Supplier(code="SUP-AGV", name="AgroVerde Guatemala", country="Guatemala", contact_email="calidad@agroverde.local", risk_level="low"),
            Supplier(code="SUP-LAA", name="Lácteos del Altiplano", country="Guatemala", contact_email="inocuidad@lacteosaltiplano.local", risk_level="medium"),
            Supplier(code="SUP-EMP", name="Empaques Centroamericanos", country="Guatemala", contact_email="trazabilidad@empaquesca.local", risk_level="low"),
        ]
        db.add_all(suppliers)
        db.flush()

        ingredients = [
            Ingredient(sku="ING-TOM-001", name="Concentrado de tomate", category="Vegetales", unit="kg", reorder_level=Decimal("250"), current_stock=Decimal("820"), supplier_id=suppliers[0].id),
            Ingredient(sku="ING-AZU-001", name="Azúcar refinada", category="Endulzantes", unit="kg", reorder_level=Decimal("120"), current_stock=Decimal("310"), supplier_id=suppliers[0].id),
            Ingredient(sku="ING-LAC-001", name="Crema láctea UHT", category="Lácteos", unit="L", allergen="Leche", reorder_level=Decimal("180"), current_stock=Decimal("145"), supplier_id=suppliers[1].id),
            Ingredient(sku="ING-ESP-001", name="Mezcla de especias SF", category="Condimentos", unit="kg", reorder_level=Decimal("35"), current_stock=Decimal("95"), supplier_id=suppliers[0].id),
        ]
        db.add_all(ingredients)
        db.flush()
        for ingredient in ingredients:
            db.add(
                InventoryMovement(
                    ingredient_id=ingredient.id,
                    movement_type="receipt",
                    quantity_delta=ingredient.current_stock,
                    balance_after=ingredient.current_stock,
                    reference="OPENING-2026",
                    reason="Existencia inicial del escenario reproducible",
                    performed_by_user_id=admin.id if admin else None,
                )
            )

        products = [
            Product(sku="PRD-SAL-500", name="Salsa de tomate Sanoli 500 g", description="Salsa cocida de tomate con especias seleccionadas.", unit="unidad", shelf_life_days=180),
            Product(sku="PRD-CRE-1L", name="Crema de tomate Sanoli 1 L", description="Crema lista para consumo con tratamiento UHT.", unit="unidad", shelf_life_days=120),
        ]
        db.add_all(products)
        db.flush()

        salsa_recipe = Recipe(product_id=products[0].id, version=1, yield_quantity=Decimal("1000"), status="approved")
        cream_recipe = Recipe(product_id=products[1].id, version=1, yield_quantity=Decimal("800"), status="approved")
        db.add_all([salsa_recipe, cream_recipe])
        db.flush()
        db.add_all(
            [
                RecipeItem(recipe_id=salsa_recipe.id, ingredient_id=ingredients[0].id, quantity=Decimal("520")),
                RecipeItem(recipe_id=salsa_recipe.id, ingredient_id=ingredients[1].id, quantity=Decimal("85")),
                RecipeItem(recipe_id=salsa_recipe.id, ingredient_id=ingredients[3].id, quantity=Decimal("18")),
                RecipeItem(recipe_id=cream_recipe.id, ingredient_id=ingredients[0].id, quantity=Decimal("320")),
                RecipeItem(recipe_id=cream_recipe.id, ingredient_id=ingredients[2].id, quantity=Decimal("260")),
                RecipeItem(recipe_id=cream_recipe.id, ingredient_id=ingredients[3].id, quantity=Decimal("12")),
            ]
        )

        now = datetime.now(timezone.utc)
        lots = [
            ProductionLot(lot_code="SF26-SAL-0017", product_id=products[0].id, recipe_id=salsa_recipe.id, planned_quantity=Decimal("1000"), status="in_progress", scheduled_at=now - timedelta(hours=3), started_at=now - timedelta(hours=2), created_by_user_id=admin.id if admin else None),
            ProductionLot(lot_code="SF26-CRE-0008", product_id=products[1].id, recipe_id=cream_recipe.id, planned_quantity=Decimal("800"), status="quality_hold", scheduled_at=now - timedelta(days=1), started_at=now - timedelta(days=1), created_by_user_id=admin.id if admin else None),
            ProductionLot(lot_code="SF26-SAL-0016", product_id=products[0].id, recipe_id=salsa_recipe.id, planned_quantity=Decimal("1000"), actual_quantity=Decimal("992"), status="released", scheduled_at=now - timedelta(days=2), started_at=now - timedelta(days=2), completed_at=now - timedelta(days=1, hours=18), created_by_user_id=admin.id if admin else None),
        ]
        db.add_all(lots)
        db.flush()
        db.add_all(
            [
                QualityCheck(production_lot_id=lots[1].id, check_type="pH", measured_value=Decimal("5.200"), unit="pH", min_value=Decimal("4.000"), max_value=Decimal("4.600"), result="fail", notes="Retenido para investigación de desviación", inspected_by_user_id=admin.id if admin else None),
                QualityCheck(production_lot_id=lots[2].id, check_type="pH", measured_value=Decimal("4.300"), unit="pH", min_value=Decimal("4.000"), max_value=Decimal("4.600"), result="pass", notes="Parámetro dentro de especificación", inspected_by_user_id=admin.id if admin else None),
            ]
        )
        record_event(
            db,
            event_type="business.demo_seed.created",
            outcome="success",
            actor=admin,
            resource_type="business_dataset",
            resource_id="sanolifood-demo-v1",
            details={"suppliers": 3, "ingredients": 4, "products": 2, "lots": 3},
        )
        db.commit()
        logger.info("business_seed_created", extra={"event_type": "business.seed.created"})


if __name__ == "__main__":
    main()
