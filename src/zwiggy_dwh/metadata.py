"""Source Metadata Discovery and Classification Matrix Generator.

Queries source tables and generates the 18-table ingestion classification matrix
mapping each source table to its ingestion strategy, watermark column, business keys,
and look-back window parameters.
"""

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional

from zwiggy_dwh.db import ConnectionWrapper, execute_sql

logger = logging.getLogger(__name__)


@dataclass
class TableClassification:
    source_table: str
    target_bronze_table: str
    target_silver_table: str
    target_gold_table: str
    ingestion_strategy: str
    business_key: str
    primary_key_column: str
    watermark_column: Optional[str]
    secondary_watermark_column: Optional[str]
    lookback_days: int
    table_group: str


SOURCE_TABLE_CLASSIFICATIONS: List[TableClassification] = [
    TableClassification("app_orders", "br_orders", "slv_order", "fact_order", "TIMESTAMP_WATERMARK", "order_id", "order_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_order_items", "br_order_items", "slv_order_item", "fact_order_item", "TIMESTAMP_WATERMARK", "order_item_id", "order_item_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_payments", "br_payments", "slv_payment_attempt", "fact_payment_attempt", "TIMESTAMP_WATERMARK", "payment_id", "payment_id", "payment_date", None, 7, "GroupC"),
    TableClassification("app_delivery_details", "br_delivery_details", "slv_delivery", "fact_delivery", "TIMESTAMP_WATERMARK", "delivery_id", "delivery_id", "delivery_time", None, 7, "GroupC"),
    TableClassification("app_reviews", "br_reviews", "slv_review", "fact_review", "CREATED_DATE_WATERMARK", "review_id", "review_id", "created_at", None, 7, "GroupC"),
    TableClassification("app_cart", "br_cart", "slv_cart", "fact_cart_item", "TIMESTAMP_WATERMARK", "cart_id", "cart_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_cart_items", "br_cart_items", "slv_cart_item", "fact_cart_item", "TIMESTAMP_WATERMARK", "cart_item_id", "cart_item_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_customer", "br_customer", "slv_customer", "dim_customer", "TIMESTAMP_WATERMARK", "customer_id", "customer_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_user_address", "br_user_address", "slv_address", "dim_address", "TIMESTAMP_WATERMARK", "address_id", "address_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_restaurant", "br_restaurant", "slv_restaurant", "dim_restaurant", "TIMESTAMP_WATERMARK", "restaurant_id", "restaurant_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_menu_item", "br_menu_item", "slv_menu_item", "dim_menu_item", "TIMESTAMP_WATERMARK", "menu_item_id", "menu_item_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_delivery_partner", "br_delivery_partner", "slv_delivery_partner", "dim_delivery_partner", "TIMESTAMP_WATERMARK", "delivery_partner_id", "delivery_partner_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_cuisines", "br_cuisines", "slv_cuisine", "dim_cuisine", "FULL_REFERENCE", "cuisine_id", "cuisine_id", None, None, 0, "GroupA"),
    TableClassification("app_gender", "br_gender", "slv_gender", "dim_gender", "FULL_SNAPSHOT", "id", "id", None, None, 0, "GroupA"),
    TableClassification("app_order_cancellation", "br_order_cancellation", "slv_order_cancellation", "fact_order", "CREATED_DATE_WATERMARK", "cancellation_id", "cancellation_id", "created_at", None, 0, "GroupC"),
    TableClassification("app_restaurant_cuisine", "br_restaurant_cuisine", "slv_restaurant_cuisine", "dim_restaurant_cuisine", "CREATED_DATE_WATERMARK", "restaurant_cuisine_id", "restaurant_cuisine_id", "created_at", None, 0, "GroupB"),
    TableClassification("app_restaurant_owner", "br_restaurant_owner", "slv_restaurant_owner", "dim_restaurant_owner", "TIMESTAMP_WATERMARK", "owner_id", "owner_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_refunds", "br_refunds", "slv_refund", "fact_payment", "TIMESTAMP_WATERMARK", "refund_id", "refund_id", "refund_date", None, 7, "GroupC")
]


def discover_source_tables(conn: ConnectionWrapper) -> List[Dict[str, str]]:
    """Discover all app_* source tables and column counts."""
    rows = execute_sql(conn, """
        SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'app_%';
    """)
    if not rows:
        # Retry with information_schema for Postgres
        rows = execute_sql(conn, """
            SELECT table_name as name FROM information_schema.tables WHERE table_schema='app' OR table_name LIKE 'app_%';
        """)
    return rows


def get_classification_matrix() -> List[TableClassification]:
    """Return static 18-table classification matrix."""
    return SOURCE_TABLE_CLASSIFICATIONS
