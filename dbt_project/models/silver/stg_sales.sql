-- Staged sales with date dimensions
{{ config(materialized='table') }}

SELECT
    date,
    store_id,
    sku,
    units_sold,
    demand,
    demand - units_sold AS lost_sales,
    revenue,
    is_promo,
    stockout_flag,
    
    -- Date dimensions
    DATE_TRUNC('week', date) AS week_start,
    DATE_TRUNC('month', date) AS month_start,
    DATE_TRUNC('quarter', date) AS quarter_start,
    YEAR(date) AS year,
    MONTH(date) AS month,
    DAYOFWEEK(date) AS day_of_week,
    DAYOFYEAR(date) AS day_of_year,
    
    -- Fiscal calendar (assuming fiscal year starts April)
    CASE 
        WHEN MONTH(date) >= 4 THEN YEAR(date)
        ELSE YEAR(date) - 1
    END AS fiscal_year,
    CASE 
        WHEN MONTH(date) >= 4 THEN MONTH(date) - 3
        ELSE MONTH(date) + 9
    END AS fiscal_month,
    
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ read_delta('sales') }}
WHERE units_sold IS NOT NULL