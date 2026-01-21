-- Staged suppliers with derived fields
{{ config(materialized='table') }}

SELECT
    supplier_id,
    supplier_name,
    region,
    lead_time_days,
    lead_time_std,
    reliability_score,
    unit_cost_multiplier,
    min_order_qty,
    payment_terms_days,
    CASE 
        WHEN reliability_score >= 0.95 THEN 'Excellent'
        WHEN reliability_score >= 0.85 THEN 'Good'
        WHEN reliability_score >= 0.70 THEN 'Fair'
        ELSE 'Poor'
    END AS reliability_tier,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ read_delta('suppliers') }}