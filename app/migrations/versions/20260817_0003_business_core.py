"""Create the SanoliFood operational business core.

Revision ID: 20260817_0003
Revises: 20260816_0002
Create Date: 2026-08-17 00:00:00 UTC
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260817_0003"
down_revision: Union[str, None] = "20260816_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("country", sa.String(length=80), server_default="Guatemala", nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("risk_level", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("risk_level in ('low','medium','high')", name="ck_suppliers_risk_level"),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"], unique=True)

    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("allergen", sa.String(length=120), nullable=True),
        sa.Column("reorder_level", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("current_stock", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("reorder_level >= 0", name="ck_ingredients_reorder_nonnegative"),
        sa.CheckConstraint("current_stock >= 0", name="ck_ingredients_stock_nonnegative"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name="fk_ingredients_supplier_id_suppliers", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_ingredients"),
        sa.UniqueConstraint("sku", name="uq_ingredients_sku"),
    )
    op.create_index("ix_ingredients_sku", "ingredients", ["sku"], unique=True)
    op.create_index("ix_ingredients_supplier_id", "ingredients", ["supplier_id"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("shelf_life_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("shelf_life_days > 0", name="ck_products_shelf_life_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("yield_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_recipes_version_positive"),
        sa.CheckConstraint("yield_quantity > 0", name="ck_recipes_yield_positive"),
        sa.CheckConstraint("status in ('draft','approved','retired')", name="ck_recipes_status"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_recipes_product_id_products", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_recipes"),
        sa.UniqueConstraint("product_id", "version", name="uq_recipes_product_version"),
    )
    op.create_index("ix_recipes_product_id", "recipes", ["product_id"], unique=False)

    op.create_table(
        "recipe_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_recipe_items_quantity_positive"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], name="fk_recipe_items_ingredient_id_ingredients", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], name="fk_recipe_items_recipe_id_recipes", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_recipe_items"),
        sa.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_items_recipe_ingredient"),
    )
    op.create_index("ix_recipe_items_ingredient_id", "recipe_items", ["ingredient_id"], unique=False)
    op.create_index("ix_recipe_items_recipe_id", "recipe_items", ["recipe_id"], unique=False)

    op.create_table(
        "production_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_code", sa.String(length=40), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="planned", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("planned_quantity > 0", name="ck_production_lots_planned_positive"),
        sa.CheckConstraint("actual_quantity is null or actual_quantity >= 0", name="ck_production_lots_actual_nonnegative"),
        sa.CheckConstraint("status in ('planned','in_progress','quality_hold','released','rejected')", name="ck_production_lots_status"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_production_lots_created_by_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_production_lots_product_id_products", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], name="fk_production_lots_recipe_id_recipes", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_production_lots"),
        sa.UniqueConstraint("lot_code", name="uq_production_lots_lot_code"),
    )
    op.create_index("ix_production_lots_created_by_user_id", "production_lots", ["created_by_user_id"], unique=False)
    op.create_index("ix_production_lots_lot_code", "production_lots", ["lot_code"], unique=True)
    op.create_index("ix_production_lots_product_id", "production_lots", ["product_id"], unique=False)
    op.create_index("ix_production_lots_recipe_id", "production_lots", ["recipe_id"], unique=False)
    op.create_index("ix_production_lots_status", "production_lots", ["status"], unique=False)

    op.create_table(
        "quality_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("production_lot_id", sa.Integer(), nullable=False),
        sa.Column("check_type", sa.String(length=60), nullable=False),
        sa.Column("measured_value", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("min_value", sa.Numeric(14, 3), nullable=False),
        sa.Column("max_value", sa.Numeric(14, 3), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("inspected_by_user_id", sa.Integer(), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_value <= max_value", name="ck_quality_checks_limits"),
        sa.CheckConstraint("result in ('pass','fail')", name="ck_quality_checks_result"),
        sa.ForeignKeyConstraint(["inspected_by_user_id"], ["users.id"], name="fk_quality_checks_inspected_by_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_lot_id"], ["production_lots.id"], name="fk_quality_checks_production_lot_id_production_lots", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_quality_checks"),
    )
    op.create_index("ix_quality_checks_inspected_by_user_id", "quality_checks", ["inspected_by_user_id"], unique=False)
    op.create_index("ix_quality_checks_production_lot_id", "quality_checks", ["production_lot_id"], unique=False)
    op.create_index("ix_quality_checks_result", "quality_checks", ["result"], unique=False)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(length=24), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity_delta != 0", name="ck_inventory_movements_quantity_nonzero"),
        sa.CheckConstraint("balance_after >= 0", name="ck_inventory_movements_balance_nonnegative"),
        sa.CheckConstraint("movement_type in ('receipt','consumption','adjustment','quarantine','release')", name="ck_inventory_movements_type"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], name="fk_inventory_movements_ingredient_id_ingredients", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], name="fk_inventory_movements_performed_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_movements"),
    )
    op.create_index("ix_inventory_movements_ingredient_id", "inventory_movements", ["ingredient_id"], unique=False)
    op.create_index("ix_inventory_movements_movement_type", "inventory_movements", ["movement_type"], unique=False)
    op.create_index("ix_inventory_movements_occurred_at", "inventory_movements", ["occurred_at"], unique=False)
    op.create_index("ix_inventory_movements_performed_by_user_id", "inventory_movements", ["performed_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_table("quality_checks")
    op.drop_table("production_lots")
    op.drop_table("recipe_items")
    op.drop_table("recipes")
    op.drop_table("products")
    op.drop_table("ingredients")
    op.drop_table("suppliers")
