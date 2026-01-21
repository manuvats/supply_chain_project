-- Staged products with derived fields
{{ config(materialized='table') }}

SELECT
    sku,
    product_name,
    category,
    unit_cost,
    unit_price,
    unit_price - unit_cost AS unit_margin,
    ROUND((unit_price - unit_cost) / NULLIF(unit_price, 0) * 100, 2) AS margin_pct,
    unit_weight_kg,
    shelf_life_days,
    is_hazardous,
    abc_class,
    safety_stock_days,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ read_delta('products') }}