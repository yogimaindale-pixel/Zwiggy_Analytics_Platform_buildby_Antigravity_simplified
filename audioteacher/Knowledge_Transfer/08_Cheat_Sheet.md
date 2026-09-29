# ⚡ 08. Zwiggy Data Warehouse Cheat Sheet & Quick Reference

Welcome to **Lesson 08: Operational Cheat Sheet**!

---

## 🛠️ CLI Quick Commands Reference

| Operation | CLI Command | Purpose |
| :--- | :--- | :--- |
| **Run Full Pipeline** | `python3 -m zwiggy_dwh.cli run-all` | Executes full 5-stage Medallion pipeline end-to-end. |
| **Seed Source DB** | `python3 -m zwiggy_dwh.cli seed-source` | Generates 61,777 realistic food delivery transactions. |
| **Init DWH Foundation**| `python3 -m zwiggy_dwh.cli init-db` | Creates all Bronze, Silver, Gold, and Control schemas. |
| **Run Ingestion** | `python3 -m zwiggy_dwh.cli ingest` | Extracts source deltas into Bronze raw landing tables. |
| **Run Transformations**| `python3 -m zwiggy_dwh.cli transform` | Transforms Bronze to Silver clean and Silver to Gold Star Schema. |
| **Reconciliation Audit**| `python3 -m zwiggy_dwh.cli reconcile` | Verifies row counts and metric sums across layers. |
| **Data Quality Scorecard**|`python3 -m zwiggy_dwh.cli scorecard` | Displays DQ rules evaluated and completeness metrics. |
| **Health Diagnostic** | `python3 -m zwiggy_dwh.cli health-check` | Tests DB connectivity, schema existence, and disk space. |
| **Simulate 10-Day CDC** | `python3 -m zwiggy_dwh.cli simulate-10-days` | Runs 10 days of incremental CDC delta generation. |
| **Run Pytest Suite** | `pytest tests/` | Runs all 12 automated unit and integration tests. |

---

## 📐 Key Mathematical & SQL Formulas

### 1. Data Completeness Percentage
$$\text{Completeness } (\%) = \left( 1 - \frac{\text{Null Required Fields}}{\text{Total Required Fields}} \right) \times 100$$

### 2. High-Watermark Incremental Bound
$$\text{Delta Extract} = \{ r \in \text{SourceTable} \mid W_{\text{last}} < r.\text{updated\_at} \le W_{\text{current}} \}$$

### 3. SCD Type 2 Active Record Filter
$$\text{Active Dimension Row} = \text{WHERE } \text{is\_current} = 1 \text{ AND } \text{effective\_to} = \text{'9999-12-31'}$$
