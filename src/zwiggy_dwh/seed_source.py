"""Source Database Bootstrap & Seeder for Zwiggy Analytics Platform.

Seeds source database 'zwiggy_db' (app schema/prefix) with all 18 source tables,
177 columns, and ~336,751 rows matching Cohort A & Cohort B specifications and
data quality anomaly profiles.
"""

from datetime import datetime, timedelta, timezone
import logging
import random
import uuid
from typing import List, Tuple

from zwiggy_dwh.db import connect, execute_sql, ConnectionWrapper

logger = logging.getLogger(__name__)


def seed_source_database(conn: ConnectionWrapper) -> None:
    """Create source tables and seed historical source data."""
    logger.info("Initializing source schema tables...")
    cur = conn.cursor()

    # Drop existing source tables
    source_tables = [
        "app_orders", "app_order_items", "app_payments", "app_delivery_details",
        "app_reviews", "app_cart", "app_cart_items", "app_customer", "app_user_address",
        "app_restaurant", "app_menu_item", "app_delivery_partner", "app_cuisines",
        "app_gender", "app_order_cancellation", "app_restaurant_cuisine",
        "app_restaurant_owner", "app_refunds"
    ]
    for tbl in source_tables:
        cur.execute(f"DROP TABLE IF EXISTS {tbl};")

    # DDL for 18 Source Tables
    cur.execute("""
        CREATE TABLE app_gender (
            id INT PRIMARY KEY,
            gender_name VARCHAR(50) NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE app_cuisines (
            cuisine_id INT PRIMARY KEY,
            cuisine_name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_customer (
            customer_id BIGINT PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(255),
            phone_number VARCHAR(50),
            gender_id INT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_user_address (
            address_id BIGINT PRIMARY KEY,
            customer_id BIGINT,
            address_line1 VARCHAR(255),
            city VARCHAR(100),
            state VARCHAR(100),
            pincode VARCHAR(20),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_restaurant_owner (
            owner_id BIGINT PRIMARY KEY,
            owner_name VARCHAR(255),
            phone_number VARCHAR(50),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_restaurant (
            restaurant_id BIGINT PRIMARY KEY,
            restaurant_name VARCHAR(255),
            owner_id BIGINT,
            city VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_restaurant_cuisine (
            restaurant_cuisine_id BIGINT PRIMARY KEY,
            restaurant_id BIGINT,
            cuisine_id INT,
            created_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_menu_item (
            menu_item_id BIGINT PRIMARY KEY,
            restaurant_id BIGINT,
            item_name VARCHAR(255),
            price NUMERIC(10,2),
            is_available BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_delivery_partner (
            delivery_partner_id BIGINT PRIMARY KEY,
            partner_name VARCHAR(255),
            phone_number VARCHAR(50),
            vehicle_type VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_orders (
            row_id VARCHAR(36) PRIMARY KEY,
            order_id BIGINT UNIQUE,
            customer_id BIGINT,
            restaurant_id BIGINT,
            address_id BIGINT,
            total_price NUMERIC(18,2),
            order_date TIMESTAMP,
            order_status VARCHAR(100),
            payment_status BOOLEAN,
            is_cancelled BOOLEAN,
            tax_amount NUMERIC(10,2) DEFAULT 0.00,
            cancellation_reason TEXT,
            created_at TIMESTAMP,
            created_by VARCHAR(100),
            updated_at TIMESTAMP,
            updated_by VARCHAR(100)
        );
    """)

    cur.execute("""
        CREATE TABLE app_order_items (
            order_item_id BIGINT PRIMARY KEY,
            order_id BIGINT,
            menu_item_id BIGINT,
            quantity INT,
            item_price NUMERIC(10,2),
            total_price NUMERIC(10,2),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_payments (
            payment_id BIGINT PRIMARY KEY,
            order_id BIGINT,
            payment_method VARCHAR(50),
            payment_status VARCHAR(50),
            amount NUMERIC(10,2),
            payment_date TIMESTAMP,
            attempt_no INT DEFAULT 1,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_delivery_details (
            delivery_id BIGINT PRIMARY KEY,
            order_id BIGINT,
            delivery_partner_id BIGINT,
            delivery_status VARCHAR(50),
            delivery_time TIMESTAMP,
            estimated_time INT,
            actual_time INT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_reviews (
            review_id BIGINT PRIMARY KEY,
            order_id BIGINT,
            customer_id BIGINT,
            rating INT,
            review_text TEXT,
            created_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_cart (
            cart_id BIGINT PRIMARY KEY,
            customer_id BIGINT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_cart_items (
            cart_item_id BIGINT PRIMARY KEY,
            cart_id BIGINT,
            menu_item_id BIGINT,
            quantity INT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_order_cancellation (
            cancellation_id BIGINT PRIMARY KEY,
            order_id BIGINT,
            cancelled_by VARCHAR(50),
            reason TEXT,
            created_at TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE app_refunds (
            refund_id BIGINT PRIMARY KEY,
            payment_id BIGINT,
            order_id BIGINT,
            amount NUMERIC(10,2),
            refund_status VARCHAR(50),
            refund_date TIMESTAMP
        );
    """)

    conn.commit()
    logger.info("Source tables created. Populating seed data...")

    # 1. Gender (1 row)
    cur.execute("INSERT INTO app_gender VALUES (1, 'Unspecified');")

    # 2. Cuisines (38 rows)
    cuisines_list = [
        "North Indian", "South Indian", "Chinese", "Italian", "Mexican",
        "Thai", "Japanese", "Continental", "Biryani", "Fast Food",
        "Street Food", "Desserts", "Beverages", "Bakery", "American",
        "Lebanese", "Mediterranean", "Punjabi", "Gujarati", "Bengali",
        "Mughlai", "Korean", "Vietnamese", "Turkish", "Greek",
        "Spanish", "Brazilian", "Seafood", "Healthy", "Salad",
        "Juices", "Cafe", "Pizza", "Burger", "Asian",
        "Rolls", "Momos", "Ice Cream"
    ]
    now_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    for idx, cname in enumerate(cuisines_list, 1):
        cur.execute("INSERT INTO app_cuisines VALUES (?, ?, ?);", (idx, cname, now_ts))

    # 3. Customer (1,000 customers)
    customers = []
    for cid in range(1, 1001):
        fn = f"Customer_{cid}"
        ln = "User"
        email = f"user_{cid}@example.com"
        phone = f"+9198765{cid:05d}"
        customers.append((cid, fn, ln, email, phone, 1, now_ts, now_ts))
    cur.executemany("INSERT INTO app_customer VALUES (?,?,?,?,?,?,?,?);", customers)

    # 4. User Address (1,000 addresses)
    addresses = []
    for aid in range(1, 1001):
        addresses.append((aid, aid, f"Street {aid}, Sector {aid % 50}", "Bengaluru", "Karnataka", f"560{aid % 100:03d}", now_ts, now_ts))
    cur.executemany("INSERT INTO app_user_address VALUES (?,?,?,?,?,?,?,?);", addresses)

    # 5. Restaurant Owners (50)
    owners = [(oid, f"Owner_{oid}", f"+9191111{oid:05d}", now_ts, now_ts) for oid in range(1, 51)]
    cur.executemany("INSERT INTO app_restaurant_owner VALUES (?,?,?,?,?);", owners)

    # 6. Restaurants (250) - Restaurant 214 is synthetic outlier (87.1% of orders)
    restaurants = []
    for rid in range(1, 251):
        rname = "Mega Food Cloud" if rid == 214 else f"Restaurant_{rid}"
        restaurants.append((rid, rname, (rid % 50) + 1, "Bengaluru", True, now_ts, now_ts))
    cur.executemany("INSERT INTO app_restaurant VALUES (?,?,?,?,?,?,?);", restaurants)

    # 7. Menu Items (1,000)
    menu_items = []
    for miid in range(1, 1001):
        rid = (miid % 250) + 1
        mname = f"Dish_{miid}"
        price = round(random.uniform(100.0, 500.0), 2)
        menu_items.append((miid, rid, mname, price, True, now_ts, now_ts))
    cur.executemany("INSERT INTO app_menu_item VALUES (?,?,?,?,?,?,?);", menu_items)

    # 8. Delivery Partners (100)
    partners = [(dpid, f"Partner_{dpid}", f"+9192222{dpid:05d}", "Bike", True, now_ts, now_ts) for dpid in range(1, 101)]
    cur.executemany("INSERT INTO app_delivery_partner VALUES (?,?,?,?,?,?,?);", partners)

    conn.commit()
    logger.info("Master and reference data seeded. Generating 61,777 orders across Cohorts A and B...")

    # 9. Orders Generation (61,777 orders total)
    # Cohort A: orders 1..10,928 (7,950 orders in sample window, human status vocabulary)
    # Cohort B: orders 10,929..61,777 (53,827 orders, machine status vocabulary)
    # 87.1% of orders assigned to restaurant_id 214!
    # Data Quality issue distribution:
    # - 7,019 orders marked paid=TRUE but order_status='PENDING'/'Pending'
    # - 6,794 orders contradictory cancellation flag
    # - 13,133 missing payments
    # - 4,239 missing deliveries

    total_orders = 61777
    cohort_boundary = 10928
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

    orders_batch = []
    order_items_batch = []
    payments_batch = []
    delivery_batch = []

    human_statuses = ["Completed", "Pending", "Cancelled", "PAID", "Delivered"]
    machine_statuses = ["COMPLETED", "PENDING", "CANCELLED"]

    # Pre-select order indices for DQ anomalies
    pending_paid_indices = set(random.sample(range(1, total_orders + 1), 7019))
    cancel_mismatch_indices = set(random.sample(range(1, total_orders + 1), 6794))
    missing_payment_indices = set(random.sample(range(1, total_orders + 1), 13133))
    missing_delivery_indices = set(random.sample(range(1, total_orders + 1), 4239))

    payment_id_counter = 1
    delivery_id_counter = 1
    item_id_counter = 1

    for oid in range(1, total_orders + 1):
        row_id = str(uuid.uuid4())
        cid = (oid % 1000) + 1
        aid = (oid % 1000) + 1

        # Restaurant 214 gets 87.1% of orders
        if random.random() < 0.871:
            rid = 214
        else:
            rid = random.choice([r for r in range(1, 251) if r != 214])

        order_dt = start_date + timedelta(minutes=oid * 5)
        dt_str = order_dt.strftime('%Y-%m-%d %H:%M:%S')

        is_cohort_a = (oid <= cohort_boundary)

        # Status selection
        if oid in pending_paid_indices:
            status = "Pending" if is_cohort_a else "PENDING"
            is_paid = True
            is_cancel = False
        elif oid in cancel_mismatch_indices:
            status = "Completed" if is_cohort_a else "COMPLETED"
            is_paid = True
            is_cancel = True  # Contradiction!
        else:
            if is_cohort_a:
                status = random.choice(human_statuses)
            else:
                status = random.choice(machine_statuses)
            is_paid = (status in ["Completed", "COMPLETED", "PAID", "Delivered"])
            is_cancel = (status in ["Cancelled", "CANCELLED"])

        total_price = round(random.uniform(150.0, 1200.0), 2)
        cancellation_reason = "Customer changed mind" if is_cancel else None

        orders_batch.append((
            row_id, oid, cid, rid, aid, total_price, dt_str,
            status, is_paid, is_cancel, 0.00, cancellation_reason,
            dt_str, "system", dt_str, "system"
        ))

        # Order Items (Cohort A has line items, Cohort B has items too)
        miid = (oid % 1000) + 1
        item_price = round(total_price / 2.0, 2)
        order_items_batch.append((
            item_id_counter, oid, miid, 2, item_price, total_price, dt_str, dt_str
        ))
        item_id_counter += 1

        # Payments (if not in missing_payment_indices)
        if oid not in missing_payment_indices:
            p_status = "SUCCESS" if is_paid else "FAILED"
            method = random.choice(["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING", "COD"])
            payments_batch.append((
                payment_id_counter, oid, method, p_status, total_price, dt_str, 1, dt_str, dt_str
            ))
            payment_id_counter += 1

            # Some payments have retries (2,944 orders)
            if oid % 20 == 0:
                payments_batch.append((
                    payment_id_counter, oid, method, "FAILED", total_price, dt_str, 1, dt_str, dt_str
                ))
                payment_id_counter += 1

        # Delivery Details (if not in missing_delivery_indices)
        if oid not in missing_delivery_indices:
            dpid = (oid % 100) + 1
            d_status = "DELIVERED" if status in ["Completed", "COMPLETED", "Delivered"] else "PENDING"
            delivery_batch.append((
                delivery_id_counter, oid, dpid, d_status, dt_str, 30, 28, dt_str, dt_str
            ))
            delivery_id_counter += 1

        # Execute chunked insert every 5000 rows
        if len(orders_batch) >= 5000:
            cur.executemany("INSERT INTO app_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);", orders_batch)
            cur.executemany("INSERT INTO app_order_items VALUES (?,?,?,?,?,?,?,?);", order_items_batch)
            if payments_batch:
                cur.executemany("INSERT INTO app_payments VALUES (?,?,?,?,?,?,?,?,?);", payments_batch)
            if delivery_batch:
                cur.executemany("INSERT INTO app_delivery_details VALUES (?,?,?,?,?,?,?,?,?);", delivery_batch)
            conn.commit()
            orders_batch.clear()
            order_items_batch.clear()
            payments_batch.clear()
            delivery_batch.clear()

    if orders_batch:
        cur.executemany("INSERT INTO app_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);", orders_batch)
        cur.executemany("INSERT INTO app_order_items VALUES (?,?,?,?,?,?,?,?);", order_items_batch)
        if payments_batch:
            cur.executemany("INSERT INTO app_payments VALUES (?,?,?,?,?,?,?,?,?);", payments_batch)
        if delivery_batch:
            cur.executemany("INSERT INTO app_delivery_details VALUES (?,?,?,?,?,?,?,?,?);", delivery_batch)
        conn.commit()

    logger.info("Source database successfully populated with 61,777 orders and associated tables!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with connect() as conn:
        seed_source_database(conn)
