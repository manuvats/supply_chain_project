-- Weekly sales aggregation
{{ config(materialized='table') }}

SELECT
    week_start,
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
    SUM(CASE WHEN is_promo THEN revenue ELSE 0 END) AS promo_revenue,
    
    -- Stockout metrics
    SUM(CASE WHEN stockout_flag THEN 1 ELSE 0 END) AS stockout_days,
    ROUND(SUM(lost_sales) / NULLIF(SUM(demand), 0) * 100, 2) AS lost_sales_pct,
    
    -- Fill rate
    ROUND(SUM(units_sold) / NULLIF(SUM(demand), 0) * 100, 2) AS fill_rate,
    
    -- Daily averages
    ROUND(AVG(units_sold), 2) AS avg_daily_units,
    ROUND(AVG(revenue), 2) AS avg_daily_revenue,
    
    COUNT(*) AS num_days

FROM {{ ref('stg_sales') }}
GROUP BY week_start, store_id, sku