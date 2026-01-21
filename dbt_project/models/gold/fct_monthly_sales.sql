-- Monthly sales aggregation
{{ config(materialized='table') }}

SELECT
    month_start,
    year,
    month,
    store_id,
    sku,
    
    -- Volume metrics
    SUM(units_sold) AS total_units,
    SUM(demand) AS total_demand,
    SUM(lost_sales) AS total_lost_sales,
    
    -- Financial metrics
    ROUND(SUM(revenue), 2) AS total_revenue,
    
    -- Promo metrics
    SUM(CASE WHEN is_promo THEN units_sold ELSE 0 END) AS promo_units,
    ROUND(SUM(CASE WHEN is_promo THEN revenue ELSE 0 END), 2) AS promo_revenue,
    
    -- Stockout metrics
    SUM(CASE WHEN stockout_flag THEN 1 ELSE 0 END) AS stockout_days,
    COUNT(*) AS total_days,
    ROUND(SUM(CASE WHEN stockout_flag THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS stockout_rate,
    
    -- Fill rate
    ROUND(SUM(units_sold) / NULLIF(SUM(demand), 0) * 100, 2) AS fill_rate

FROM {{ ref('stg_sales') }}
GROUP BY month_start, year, month, store_id, sku