from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from sanolifood.core.events import record_event
from sanolifood.core.security import csrf_is_valid
from sanolifood.database.session import get_db
from sanolifood.models import Ingredient, InventoryMovement, Supplier, User, UserRole
from sanolifood.services.operations import MOVEMENT_TYPES, decimal_value, record_stock_movement
from sanolifood.web.dependencies import PermissionDenied, get_current_user, require_roles
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/inventory", tags=["inventory"])
inventory_write_required = require_roles(UserRole.ADMIN, UserRole.WAREHOUSE)


def inventory_response(
    request: Request,
    db: Session,
    current_user: User,
    *,
    errors: list[str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    suppliers = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    ingredients = db.scalars(select(Ingredient).order_by(Ingredient.name)).unique().all()
    movements = db.scalars(
        select(InventoryMovement).order_by(InventoryMovement.occurred_at.desc()).limit(80)
    ).unique().all()
    low_stock_count = sum(
        1 for ingredient in ingredients if Decimal(ingredient.current_stock) <= Decimal(ingredient.reorder_level)
    )
    return templates.TemplateResponse(
        request=request,
        name="inventory/list.html",
        context=view_context(
            request,
            page_title="Inventario y abastecimiento",
            current_user=current_user,
            nav_active="inventory",
            suppliers=suppliers,
            ingredients=ingredients,
            movements=movements,
            movement_types=sorted(MOVEMENT_TYPES),
            low_stock_count=low_stock_count,
            can_write=current_user.role in {UserRole.ADMIN, UserRole.WAREHOUSE},
            errors=errors or [],
            created=request.query_params.get("created", ""),
        ),
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def inventory_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return inventory_response(request, db, current_user)


@router.post("/suppliers", include_in_schema=False)
def create_supplier(
    request: Request,
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    country: Annotated[str, Form()],
    contact_email: Annotated[str, Form()],
    risk_level: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(inventory_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación del proveedor no superó la validación de seguridad.")
    normalized_code = code.strip().upper()
    errors: list[str] = []
    if len(normalized_code) < 3 or len(name.strip()) < 3:
        errors.append("El código y nombre del proveedor no son válidos.")
    if risk_level not in {"low", "medium", "high"}:
        errors.append("El nivel de riesgo seleccionado no es válido.")
    if contact_email.strip() and "@" not in contact_email:
        errors.append("El correo del proveedor no es válido.")
    if db.scalar(select(Supplier.id).where(Supplier.code == normalized_code)) is not None:
        errors.append("Ya existe un proveedor con ese código.")
    if errors:
        return inventory_response(request, db, current_user, errors=errors, status_code=422)

    supplier = Supplier(
        code=normalized_code,
        name=name.strip(),
        country=country.strip() or "Guatemala",
        contact_email=contact_email.strip().lower() or None,
        risk_level=risk_level,
    )
    db.add(supplier)
    db.flush()
    record_event(
        db,
        request=request,
        event_type="inventory.supplier.created",
        outcome="success",
        actor=current_user,
        resource_type="supplier",
        resource_id=str(supplier.id),
        details={"code": supplier.code, "risk_level": supplier.risk_level},
    )
    db.commit()
    return RedirectResponse(url="/inventory?created=supplier", status_code=303)


@router.post("/ingredients", include_in_schema=False)
def create_ingredient(
    request: Request,
    sku: Annotated[str, Form()],
    name: Annotated[str, Form()],
    category: Annotated[str, Form()],
    unit: Annotated[str, Form()],
    allergen: Annotated[str, Form()],
    reorder_level: Annotated[str, Form()],
    supplier_id: Annotated[int, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(inventory_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación del ingrediente no superó la validación de seguridad.")
    errors: list[str] = []
    normalized_sku = sku.strip().upper()
    try:
        reorder = decimal_value(reorder_level)
        if reorder < 0:
            errors.append("El punto de reposición no puede ser negativo.")
    except ValueError as exc:
        errors.append(str(exc))
        reorder = Decimal("0")
    supplier = db.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active:
        errors.append("Selecciona un proveedor activo.")
    if len(normalized_sku) < 3 or len(name.strip()) < 3 or not unit.strip():
        errors.append("SKU, nombre y unidad son obligatorios.")
    if db.scalar(select(Ingredient.id).where(Ingredient.sku == normalized_sku)) is not None:
        errors.append("Ya existe un ingrediente con ese SKU.")
    if errors:
        return inventory_response(request, db, current_user, errors=errors, status_code=422)

    ingredient = Ingredient(
        sku=normalized_sku,
        name=name.strip(),
        category=category.strip() or "General",
        unit=unit.strip(),
        allergen=allergen.strip() or None,
        reorder_level=reorder,
        current_stock=Decimal("0"),
        supplier_id=supplier_id,
    )
    db.add(ingredient)
    db.flush()
    record_event(
        db,
        request=request,
        event_type="inventory.ingredient.created",
        outcome="success",
        actor=current_user,
        resource_type="ingredient",
        resource_id=str(ingredient.id),
        details={"sku": ingredient.sku, "supplier_code": supplier.code},
    )
    db.commit()
    return RedirectResponse(url="/inventory?created=ingredient", status_code=303)


@router.post("/movements", include_in_schema=False)
def create_movement(
    request: Request,
    ingredient_id: Annotated[int, Form()],
    movement_type: Annotated[str, Form()],
    quantity: Annotated[str, Form()],
    reference: Annotated[str, Form()],
    reason: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(inventory_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("El movimiento de inventario no superó la validación de seguridad.")
    errors: list[str] = []
    try:
        parsed_quantity = decimal_value(quantity, nonzero=True)
    except ValueError as exc:
        errors.append(str(exc))
        parsed_quantity = Decimal("0")
    if len(reference.strip()) < 3:
        errors.append("La referencia debe contener al menos tres caracteres.")
    if errors:
        return inventory_response(request, db, current_user, errors=errors, status_code=422)
    try:
        movement, previous_balance = record_stock_movement(
            db,
            ingredient_id=ingredient_id,
            movement_type=movement_type,
            quantity=parsed_quantity,
            reference=reference,
            reason=reason,
            actor=current_user,
        )
    except ValueError as exc:
        db.rollback()
        return inventory_response(request, db, current_user, errors=[str(exc)], status_code=422)

    event_type = "inventory.movement.recorded"
    if movement_type == "adjustment" and abs(Decimal(movement.quantity_delta)) >= Decimal("100"):
        event_type = "inventory.adjustment.high_value"
    record_event(
        db,
        request=request,
        event_type=event_type,
        outcome="success",
        actor=current_user,
        resource_type="inventory_movement",
        resource_id=str(movement.id),
        details={
            "ingredient_id": movement.ingredient_id,
            "movement_type": movement.movement_type,
            "quantity_delta": str(movement.quantity_delta),
            "previous_balance": str(previous_balance),
            "balance_after": str(movement.balance_after),
            "reference": movement.reference,
        },
    )
    db.commit()
    return RedirectResponse(url="/inventory?created=movement", status_code=303)
