from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from sanolifood.core.events import record_event
from sanolifood.core.security import csrf_is_valid
from sanolifood.database.session import get_db
from sanolifood.models import Ingredient, Product, ProductionLot, Recipe, RecipeItem, User, UserRole
from sanolifood.services.operations import decimal_value, transition_lot
from sanolifood.web.dependencies import PermissionDenied, get_current_user, require_roles
from sanolifood.web.templates import templates, view_context


router = APIRouter(prefix="/production", tags=["production"])
production_write_required = require_roles(UserRole.ADMIN, UserRole.PRODUCTION)
recipe_approval_required = require_roles(UserRole.ADMIN, UserRole.QUALITY)


def production_response(
    request: Request,
    db: Session,
    current_user: User,
    *,
    errors: list[str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    products = db.scalars(select(Product).order_by(Product.name)).all()
    recipes = db.scalars(select(Recipe).order_by(Recipe.created_at.desc())).unique().all()
    ingredients = db.scalars(select(Ingredient).where(Ingredient.is_active.is_(True)).order_by(Ingredient.name)).all()
    lots = db.scalars(
        select(ProductionLot).order_by(ProductionLot.scheduled_at.desc()).limit(80)
    ).unique().all()
    return templates.TemplateResponse(
        request=request,
        name="production/list.html",
        context=view_context(
            request,
            page_title="Producción y trazabilidad",
            current_user=current_user,
            nav_active="production",
            products=products,
            recipes=recipes,
            ingredients=ingredients,
            lots=lots,
            can_produce=current_user.role in {UserRole.ADMIN, UserRole.PRODUCTION},
            can_approve_recipe=current_user.role in {UserRole.ADMIN, UserRole.QUALITY},
            errors=errors or [],
            created=request.query_params.get("created", ""),
        ),
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def production_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return production_response(request, db, current_user)


@router.post("/products", include_in_schema=False)
def create_product(
    request: Request,
    sku: Annotated[str, Form()],
    name: Annotated[str, Form()],
    description: Annotated[str, Form()],
    unit: Annotated[str, Form()],
    shelf_life_days: Annotated[int, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(production_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación del producto no superó la validación de seguridad.")
    normalized_sku = sku.strip().upper()
    errors: list[str] = []
    if len(normalized_sku) < 3 or len(name.strip()) < 3 or not unit.strip():
        errors.append("SKU, nombre y unidad son obligatorios.")
    if shelf_life_days <= 0 or shelf_life_days > 3650:
        errors.append("La vida útil debe estar entre 1 y 3650 días.")
    if db.scalar(select(Product.id).where(Product.sku == normalized_sku)) is not None:
        errors.append("Ya existe un producto con ese SKU.")
    if errors:
        return production_response(request, db, current_user, errors=errors, status_code=422)
    product = Product(
        sku=normalized_sku,
        name=name.strip(),
        description=description.strip() or None,
        unit=unit.strip(),
        shelf_life_days=shelf_life_days,
    )
    db.add(product)
    db.flush()
    record_event(db, request=request, event_type="production.product.created", outcome="success", actor=current_user, resource_type="product", resource_id=str(product.id), details={"sku": product.sku})
    db.commit()
    return RedirectResponse(url="/production?created=product", status_code=303)


@router.post("/recipes", include_in_schema=False)
def create_recipe(
    request: Request,
    product_id: Annotated[int, Form()],
    version: Annotated[int, Form()],
    yield_quantity: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(production_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación de la receta no superó la validación de seguridad.")
    errors: list[str] = []
    try:
        parsed_yield = decimal_value(yield_quantity, positive=True)
    except ValueError as exc:
        errors.append(str(exc))
        parsed_yield = Decimal("0")
    if version <= 0:
        errors.append("La versión debe ser mayor que cero.")
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        errors.append("Selecciona un producto activo.")
    duplicate = db.scalar(select(Recipe.id).where(Recipe.product_id == product_id, Recipe.version == version))
    if duplicate is not None:
        errors.append("Ya existe esa versión de receta para el producto.")
    if errors:
        return production_response(request, db, current_user, errors=errors, status_code=422)
    recipe = Recipe(product_id=product_id, version=version, yield_quantity=parsed_yield, status="draft")
    db.add(recipe)
    db.flush()
    record_event(db, request=request, event_type="production.recipe.created", outcome="success", actor=current_user, resource_type="recipe", resource_id=str(recipe.id), details={"product_sku": product.sku, "version": version})
    db.commit()
    return RedirectResponse(url="/production?created=recipe", status_code=303)


@router.post("/recipes/{recipe_id}/items", include_in_schema=False)
def add_recipe_item(
    recipe_id: int,
    request: Request,
    ingredient_id: Annotated[int, Form()],
    quantity: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(production_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La modificación de la receta no superó la validación de seguridad.")
    recipe = db.get(Recipe, recipe_id)
    errors: list[str] = []
    if recipe is None:
        errors.append("La receta solicitada no existe.")
    elif recipe.status != "draft":
        errors.append("Solo pueden modificarse recetas en borrador.")
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None or not ingredient.is_active:
        errors.append("Selecciona un ingrediente activo.")
    try:
        parsed_quantity = decimal_value(quantity, positive=True)
    except ValueError as exc:
        errors.append(str(exc))
        parsed_quantity = Decimal("0")
    duplicate = db.scalar(select(RecipeItem.id).where(RecipeItem.recipe_id == recipe_id, RecipeItem.ingredient_id == ingredient_id))
    if duplicate is not None:
        errors.append("Ese ingrediente ya pertenece a la receta.")
    if errors:
        return production_response(request, db, current_user, errors=errors, status_code=422)
    item = RecipeItem(recipe_id=recipe_id, ingredient_id=ingredient_id, quantity=parsed_quantity)
    db.add(item)
    db.flush()
    record_event(db, request=request, event_type="production.recipe.item_added", outcome="success", actor=current_user, resource_type="recipe", resource_id=str(recipe_id), details={"ingredient_sku": ingredient.sku, "quantity": str(parsed_quantity)})
    db.commit()
    return RedirectResponse(url="/production?created=recipe_item", status_code=303)


@router.post("/recipes/{recipe_id}/approve", include_in_schema=False)
def approve_recipe(
    recipe_id: int,
    request: Request,
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(recipe_approval_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La aprobación de la receta no superó la validación de seguridad.")
    recipe = db.get(Recipe, recipe_id)
    errors: list[str] = []
    if recipe is None or recipe.status != "draft":
        errors.append("La receta no existe o ya no está en borrador.")
    elif db.scalar(select(RecipeItem.id).where(RecipeItem.recipe_id == recipe_id).limit(1)) is None:
        errors.append("La receta requiere al menos un ingrediente antes de aprobarse.")
    if errors:
        return production_response(request, db, current_user, errors=errors, status_code=422)
    recipe.status = "approved"
    record_event(db, request=request, event_type="production.recipe.approved", outcome="success", actor=current_user, resource_type="recipe", resource_id=str(recipe.id), details={"product_sku": recipe.product.sku, "version": recipe.version})
    db.commit()
    return RedirectResponse(url="/production?created=recipe_approved", status_code=303)


@router.post("/lots", include_in_schema=False)
def create_lot(
    request: Request,
    lot_code: Annotated[str, Form()],
    product_id: Annotated[int, Form()],
    planned_quantity: Annotated[str, Form()],
    scheduled_at: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(production_write_required),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La creación del lote no superó la validación de seguridad.")
    errors: list[str] = []
    normalized_code = lot_code.strip().upper()
    try:
        parsed_quantity = decimal_value(planned_quantity, positive=True)
    except ValueError as exc:
        errors.append(str(exc))
        parsed_quantity = Decimal("0")
    try:
        parsed_schedule = datetime.fromisoformat(scheduled_at)
        if parsed_schedule.tzinfo is None:
            parsed_schedule = parsed_schedule.replace(tzinfo=timezone.utc)
    except ValueError:
        errors.append("La fecha programada no es válida.")
        parsed_schedule = datetime.now(timezone.utc)
    product = db.get(Product, product_id)
    approved_recipe = db.scalar(
        select(Recipe)
        .where(Recipe.product_id == product_id, Recipe.status == "approved")
        .order_by(Recipe.version.desc())
        .limit(1)
    )
    if product is None or not product.is_active:
        errors.append("Selecciona un producto activo.")
    elif approved_recipe is None:
        errors.append("El producto necesita una receta aprobada antes de planificar lotes.")
    if len(normalized_code) < 6:
        errors.append("El código de lote debe contener al menos seis caracteres.")
    if db.scalar(select(ProductionLot.id).where(ProductionLot.lot_code == normalized_code)) is not None:
        errors.append("Ya existe un lote con ese código.")
    if errors:
        return production_response(request, db, current_user, errors=errors, status_code=422)
    lot = ProductionLot(lot_code=normalized_code, product_id=product_id, recipe_id=approved_recipe.id, planned_quantity=parsed_quantity, status="planned", scheduled_at=parsed_schedule, created_by_user_id=current_user.id)
    db.add(lot)
    db.flush()
    record_event(db, request=request, event_type="production.lot.created", outcome="success", actor=current_user, resource_type="production_lot", resource_id=str(lot.id), details={"lot_code": lot.lot_code, "product_sku": product.sku, "planned_quantity": str(lot.planned_quantity)})
    db.commit()
    return RedirectResponse(url="/production?created=lot", status_code=303)


@router.post("/lots/{lot_id}/transition", include_in_schema=False)
def change_lot_status(
    lot_id: int,
    request: Request,
    target_status: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not csrf_is_valid(request, csrf_token):
        raise PermissionDenied("La transición del lote no superó la validación de seguridad.")
    if target_status in {"in_progress", "quality_hold"} and current_user.role not in {UserRole.ADMIN, UserRole.PRODUCTION}:
        raise PermissionDenied("Tu rol no puede ejecutar transiciones de producción.")
    if target_status in {"released", "rejected"} and current_user.role not in {UserRole.ADMIN, UserRole.QUALITY}:
        raise PermissionDenied("Solo Calidad puede decidir la disposición final del lote.")
    try:
        lot, previous_status, material_movements = transition_lot(
            db, lot_id=lot_id, target_status=target_status, actor=current_user
        )
    except ValueError as exc:
        db.rollback()
        return production_response(request, db, current_user, errors=[str(exc)], status_code=422)
    if material_movements:
        record_event(
            db,
            request=request,
            event_type="production.lot.materials_consumed",
            outcome="success",
            actor=current_user,
            resource_type="production_lot",
            resource_id=str(lot.id),
            details={
                "lot_code": lot.lot_code,
                "recipe_version": lot.recipe.version,
                "movement_count": len(material_movements),
                "materials": [
                    {
                        "ingredient_id": movement.ingredient_id,
                        "quantity_delta": str(movement.quantity_delta),
                        "balance_after": str(movement.balance_after),
                    }
                    for movement in material_movements
                ],
            },
        )
    record_event(db, request=request, event_type="production.lot.status_changed", outcome="success", actor=current_user, resource_type="production_lot", resource_id=str(lot.id), details={"lot_code": lot.lot_code, "previous_status": previous_status, "new_status": lot.status})
    db.commit()
    return RedirectResponse(url="/production?created=transition", status_code=303)
