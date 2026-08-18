from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from sanolifood.models import Ingredient, InventoryMovement, ProductionLot, QualityCheck, User


MOVEMENT_TYPES = {"receipt", "consumption", "adjustment", "quarantine", "release"}
LOT_STATUSES = {"planned", "in_progress", "quality_hold", "released", "rejected"}
LOT_TRANSITIONS = {
    "planned": {"in_progress"},
    "in_progress": {"quality_hold"},
    "quality_hold": {"released", "rejected"},
    "released": set(),
    "rejected": set(),
}


def decimal_value(raw: str, *, positive: bool = False, nonzero: bool = False) -> Decimal:
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Ingresa una cantidad numérica válida.") from None
    if not value.is_finite():
        raise ValueError("La cantidad debe ser finita.")
    value = value.quantize(Decimal("0.001"))
    if positive and value <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    if nonzero and value == 0:
        raise ValueError("La cantidad no puede ser cero.")
    return value


def record_stock_movement(
    db: Session,
    *,
    ingredient_id: int,
    movement_type: str,
    quantity: Decimal,
    reference: str,
    reason: str | None,
    actor: User,
) -> tuple[InventoryMovement, Decimal]:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError("El tipo de movimiento no es válido.")
    ingredient = db.scalar(
        select(Ingredient).where(Ingredient.id == ingredient_id).with_for_update()
    )
    if ingredient is None or not ingredient.is_active:
        raise ValueError("El ingrediente solicitado no existe o está inactivo.")

    magnitude = abs(quantity)
    if movement_type in {"consumption", "quarantine"}:
        delta = -magnitude
    elif movement_type in {"receipt", "release"}:
        delta = magnitude
    else:
        delta = quantity
    if delta == 0:
        raise ValueError("La cantidad no puede ser cero.")

    previous_balance = Decimal(ingredient.current_stock)
    new_balance = (previous_balance + delta).quantize(Decimal("0.001"))
    if new_balance < 0:
        raise ValueError("El movimiento dejaría existencias negativas y fue rechazado.")

    ingredient.current_stock = new_balance
    movement = InventoryMovement(
        ingredient_id=ingredient.id,
        movement_type=movement_type,
        quantity_delta=delta,
        balance_after=new_balance,
        reference=reference.strip(),
        reason=reason.strip() if reason else None,
        performed_by_user_id=actor.id,
    )
    db.add(movement)
    db.flush()
    return movement, previous_balance


def transition_lot(
    db: Session,
    *,
    lot_id: int,
    target_status: str,
    actor: User,
) -> tuple[ProductionLot, str, list[InventoryMovement]]:
    if target_status not in LOT_STATUSES:
        raise ValueError("El estado de destino no es válido.")
    lot = db.scalar(select(ProductionLot).where(ProductionLot.id == lot_id).with_for_update())
    if lot is None:
        raise ValueError("El lote solicitado no existe.")
    previous_status = lot.status
    if target_status not in LOT_TRANSITIONS.get(previous_status, set()):
        raise ValueError(f"No se permite pasar de {previous_status} a {target_status}.")

    if target_status == "released":
        checks = db.scalars(
            select(QualityCheck).where(QualityCheck.production_lot_id == lot.id)
        ).all()
        if not checks:
            raise ValueError("El lote no puede liberarse sin controles de calidad.")
        if any(check.result == "fail" for check in checks):
            raise ValueError("El lote conserva controles fallidos y no puede liberarse.")
    if target_status == "rejected":
        failed_check = db.scalar(
            select(QualityCheck.id).where(
                QualityCheck.production_lot_id == lot.id,
                QualityCheck.result == "fail",
            )
        )
        if failed_check is None:
            raise ValueError("El rechazo requiere al menos un control de calidad fallido.")

    now = datetime.now(timezone.utc)
    material_movements: list[InventoryMovement] = []
    if target_status == "in_progress":
        if lot.recipe.status != "approved":
            raise ValueError("La receta asociada al lote ya no está aprobada.")
        scale = Decimal(lot.planned_quantity) / Decimal(lot.recipe.yield_quantity)
        # A stable lock order reduces deadlock risk when concurrent lots share materials.
        for item in sorted(lot.recipe.items, key=lambda recipe_item: recipe_item.ingredient_id):
            required_quantity = (Decimal(item.quantity) * scale).quantize(Decimal("0.001"))
            movement, _ = record_stock_movement(
                db,
                ingredient_id=item.ingredient_id,
                movement_type="consumption",
                quantity=required_quantity,
                reference=lot.lot_code,
                reason=f"Consumo automático de receta v{lot.recipe.version}",
                actor=actor,
            )
            material_movements.append(movement)
    lot.status = target_status
    if target_status == "in_progress":
        lot.started_at = now
    if target_status in {"released", "rejected"}:
        lot.completed_at = now
        if lot.actual_quantity is None:
            lot.actual_quantity = lot.planned_quantity
    db.flush()
    return lot, previous_status, material_movements


def register_quality_check(
    db: Session,
    *,
    lot_id: int,
    check_type: str,
    measured_value: Decimal,
    unit: str,
    min_value: Decimal,
    max_value: Decimal,
    notes: str | None,
    actor: User,
) -> tuple[QualityCheck, str]:
    if min_value > max_value:
        raise ValueError("El límite mínimo no puede superar al máximo.")
    lot = db.scalar(select(ProductionLot).where(ProductionLot.id == lot_id).with_for_update())
    if lot is None:
        raise ValueError("El lote solicitado no existe.")
    if lot.status not in {"in_progress", "quality_hold"}:
        raise ValueError("Solo se inspeccionan lotes en proceso o retenidos por calidad.")

    result = "pass" if min_value <= measured_value <= max_value else "fail"
    check = QualityCheck(
        production_lot_id=lot.id,
        check_type=check_type.strip(),
        measured_value=measured_value,
        unit=unit.strip(),
        min_value=min_value,
        max_value=max_value,
        result=result,
        notes=notes.strip() if notes else None,
        inspected_by_user_id=actor.id,
    )
    db.add(check)
    if result == "fail":
        lot.status = "quality_hold"
    db.flush()
    return check, result
