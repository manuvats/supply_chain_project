-- Product performance summary
{{ config(materialized='table') }}

WITH sales_summary AS (
    SELECT
        sku,
        SUM(total_units) AS lifetime_units,
        SUM(total_revenue) AS lifetime_revenue,
        SUM(stockout_days) AS total_stockout_days,
        SUM(total_days) AS total_days,
        COUNT(DISTINCT store_id) AS num_stores,
        MIN(month_start) AS first_sale_date,
        MAX(month_start) AS last_sale_date,
        AVG(fill_rate) AS avg_fill_rate
    FROM {{ ref('fct_monthly_sales') }}
    GROUP BY sku
),

inventory_summary AS (
    SELECT
        sku,
        AVG(on_hand_qty) AS avg_on_hand,
        AVG(inventory_value) AS avg_inventory_value,
        SUM(CASE WHEN is_stockout THEN 1 ELSE 0 END) AS stockout_snapshots,
        COUNT(*) AS total_snapshots
    FROM {{ ref('stg_inventory') }}
    GROUP BY sku
)

SELECT
    p.sku,
    p.product_name,
    p.category,
    p.abc_class,
    p.unit_cost,
    p.unit_price,
    p.margin_pct,
    
    -- Sales metrics
    COALESCE(s.lifetime_units, 0) AS lifetime_units,
    COALESCE(s.lifetime_revenue, 0) AS lifetime_revenue,
    COALESCE(s.num_stores, 0) AS num_stores,
    s.first_sale_date,
    s.last_sale_date,
    COALESCE(s.avg_fill_rate, 0) AS avg_fill_rate,
    
    -- Inventory metrics
    COALESCE(i.avg_on_hand, 0) AS avg_on_hand,
    COALESCE(i.avg_inventory_value, 0) AS avg_inventory_value,
    
    -- Service level
    ROUND(COALESCE(s.total_stockout_days, 0) * 100.0 / NULLIF(s.total_days, 0), 2) AS stockout_rate,
    ROUND(100 - COALESCE(s.total_stockout_days, 0) * 100.0 / NULLIF(s.total_days, 0), 2) AS service_level,
    
    -- Inventory health
    ROUND(COALESCE(i.stockout_snapshots, 0) * 100.0 / NULLIF(i.total_snapshots, 0), 2) AS inventory_stockout_rate,
    
    CURRENT_TIMESTAMP AS _loaded_at

FROM {{ ref('stg_products') }} p
LEFT JOIN sales_summary s ON p.sku = s.sku
LEFT JOIN inventory_summary i ON p.sku = i.sku