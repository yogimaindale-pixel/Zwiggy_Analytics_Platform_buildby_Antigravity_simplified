# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - METADATA DISCOVERY & MATRIX GENERATOR
# ==============================================================================
# File: src/zwiggy_dwh/metadata.py
# Purpose: Defines the 18-table ingestion classification matrix mapping source
#          tables to Bronze, Silver, and Gold target layers, ingestion strategies,
#          watermarks, primary keys, and SLA lookback windows.
# ==============================================================================

# Import dataclass decorator for concise class definition.
from dataclasses import dataclass

# Import standard logging module for operational logging.
import logging

# Import typing hints for type annotations.
from typing import Dict, List, Optional

# Import database connection wrapper and query utility.
from zwiggy_dwh.db import ConnectionWrapper, execute_sql

# Create standard logger instance for this module.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# TABLE CLASSIFICATION DATACLASS STRUCT
# ------------------------------------------------------------------------------

@dataclass
class TableClassification:
    """
    Data structure defining the medallion ETL mapping metadata for a single source table.
    """
    # Name of operational source table (e.g. app_orders)
    source_table: str
    
    # Target table name in raw Bronze layer (e.g. br_orders)
    target_bronze_table: str
    
    # Target table name in cleaned Silver layer (e.g. slv_order)
    target_silver_table: str
    
    # Target table name in modeled Gold layer (e.g. fact_order or dim_customer)
    target_gold_table: str
    
    # Ingestion pattern strategy (TIMESTAMP_WATERMARK, CREATED_DATE_WATERMARK, FULL_SNAPSHOT, etc.)
    ingestion_strategy: str
    
    # Logical business key column name
    business_key: str
    
    # Primary key column name in source database
    primary_key_column: str
    
    # Primary watermark column name for incremental delta extraction
    watermark_column: Optional[str]
    
    # Secondary watermark column name if dual-watermark filtering is needed
    secondary_watermark_column: Optional[str]
    
    # SLA lookback window in days for late-arriving data backfills
    lookback_days: int
    
    # Priority classification group (GroupA, GroupB, GroupC)
    table_group: str


# ------------------------------------------------------------------------------
# 18-TABLE INGESTION CLASSIFICATION MATRIX CONFIGURATION
# ------------------------------------------------------------------------------

# Define complete 18-table Metadata Matrix mapping every operational source table.
SOURCE_TABLE_CLASSIFICATIONS: List[TableClassification] = [
    # Group C: High-Volume Transactional Fact Tables
    TableClassification("app_orders", "br_orders", "slv_order", "fact_order", "TIMESTAMP_WATERMARK", "order_id", "order_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_order_items", "br_order_items", "slv_order_item", "fact_order_item", "TIMESTAMP_WATERMARK", "order_item_id", "order_item_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_payments", "br_payments", "slv_payment_attempt", "fact_payment_attempt", "TIMESTAMP_WATERMARK", "payment_id", "payment_id", "payment_date", None, 7, "GroupC"),
    TableClassification("app_delivery_details", "br_delivery_details", "slv_delivery", "fact_delivery", "TIMESTAMP_WATERMARK", "delivery_id", "delivery_id", "delivery_time", None, 7, "GroupC"),
    TableClassification("app_reviews", "br_reviews", "slv_review", "fact_review", "CREATED_DATE_WATERMARK", "review_id", "review_id", "created_at", None, 7, "GroupC"),
    TableClassification("app_cart", "br_cart", "slv_cart", "fact_cart_item", "TIMESTAMP_WATERMARK", "cart_id", "cart_id", "updated_at", None, 7, "GroupC"),
    TableClassification("app_cart_items", "br_cart_items", "slv_cart_item", "fact_cart_item", "TIMESTAMP_WATERMARK", "cart_item_id", "cart_item_id", "updated_at", None, 7, "GroupC"),
    
    # Group B: Master & Dimension Entity Tables
    TableClassification("app_customer", "br_customer", "slv_customer", "dim_customer", "TIMESTAMP_WATERMARK", "customer_id", "customer_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_user_address", "br_user_address", "slv_address", "dim_address", "TIMESTAMP_WATERMARK", "address_id", "address_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_restaurant", "br_restaurant", "slv_restaurant", "dim_restaurant", "TIMESTAMP_WATERMARK", "restaurant_id", "restaurant_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_menu_item", "br_menu_item", "slv_menu_item", "dim_menu_item", "TIMESTAMP_WATERMARK", "menu_item_id", "menu_item_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_delivery_partner", "br_delivery_partner", "slv_delivery_partner", "dim_delivery_partner", "TIMESTAMP_WATERMARK", "delivery_partner_id", "delivery_partner_id", "updated_at", None, 0, "GroupB"),
    
    # Group A: Low-Volume Reference & Lookup Tables
    TableClassification("app_cuisines", "br_cuisines", "slv_cuisine", "dim_cuisine", "FULL_REFERENCE", "cuisine_id", "cuisine_id", None, None, 0, "GroupA"),
    TableClassification("app_gender", "br_gender", "slv_gender", "dim_gender", "FULL_SNAPSHOT", "id", "id", None, None, 0, "GroupA"),
    
    # Group C / Group B Supplemental Tables
    TableClassification("app_order_cancellation", "br_order_cancellation", "slv_order_cancellation", "fact_order", "CREATED_DATE_WATERMARK", "cancellation_id", "cancellation_id", "created_at", None, 0, "GroupC"),
    TableClassification("app_restaurant_cuisine", "br_restaurant_cuisine", "slv_restaurant_cuisine", "dim_restaurant_cuisine", "CREATED_DATE_WATERMARK", "restaurant_cuisine_id", "restaurant_cuisine_id", "created_at", None, 0, "GroupB"),
    TableClassification("app_restaurant_owner", "br_restaurant_owner", "slv_restaurant_owner", "dim_restaurant_owner", "TIMESTAMP_WATERMARK", "owner_id", "owner_id", "updated_at", None, 0, "GroupB"),
    TableClassification("app_refunds", "br_refunds", "slv_refund", "fact_payment", "TIMESTAMP_WATERMARK", "refund_id", "refund_id", "refund_date", None, 7, "GroupC")
]


# ------------------------------------------------------------------------------
# METADATA DISCOVERY & RETRIEVAL FUNCTIONS
# ------------------------------------------------------------------------------

def discover_source_tables(conn: ConnectionWrapper) -> List[Dict[str, str]]:
    """
    Queries source database catalog to discover all active operational app_* tables.
    
    Args:
        conn (ConnectionWrapper): Database connection wrapper instance.
        
    Returns:
        List[Dict[str, str]]: List of table metadata dictionaries containing table names.
    """
    # Execute query against SQLite master schema table.
    rows = execute_sql(conn, """
        SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'app_%';
    """)
    
    # If SQLite query returns empty, attempt PostgreSQL information_schema search.
    if not rows:
        rows = execute_sql(conn, """
            SELECT table_name as name FROM information_schema.tables WHERE table_schema='app' OR table_name LIKE 'app_%';
        """)
        
    # Return discovered table rows.
    return rows


def get_classification_matrix() -> List[TableClassification]:
    """
    Returns the static 18-table ingestion classification matrix list.
    
    Returns:
        List[TableClassification]: Complete table metadata configuration list.
    """
    # Return pre-defined classification matrix list.
    return SOURCE_TABLE_CLASSIFICATIONS
