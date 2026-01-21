-- Staged inventory with derived metrics
{{ config(materialized='table') }}

SELECT
    snapshot_date,
    location_id,
    sku,
    on_hand_qty,
    in_transit_qty,
    backorder_qty,
    inventory_value,
    
    -- Derived fields
    on_hand_qty + in_transit_qty AS total_available_qty,
    COALESCE(on_hand_qty, 0) + COALESCE(in_transit_qty, 0) - COALESCE(backorder_qty, 0) AS net_position,
    
    -- Inventory health flags
    CASE WHEN on_hand_qty = 0 THEN TRUE ELSE FALSE END AS is_stockout,
    CASE WHEN on_hand_qty < 50 THEN TRUE ELSE FALSE END AS is_low_stock,
    
    -- Date dimensions
    DATE_TRUNC('month', snapshot_date) AS month_start,
    YEAR(snapshot_date) AS year,
    MONTH(snapshot_date) AS month,
    
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ read_delta('inventory') }}
WHERE on_hand_qty IS NOT NULL