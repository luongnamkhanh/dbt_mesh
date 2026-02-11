{{
    config(
        materialized='table'
    )
}}

-- Downstream model that references the upstream public_orders model
-- Using dbt-loom plugin for cross-project reference resolution

SELECT
    order_id,
    status,
    amount,
    created_at,
    -- Add downstream business logic
    CASE
        WHEN amount > 200 THEN 'HIGH_VALUE'
        WHEN amount > 100 THEN 'MEDIUM_VALUE'
        ELSE 'STANDARD'
    END AS order_tier,
    'dbt_down_loom' AS processed_by
FROM {{ ref('dbt_up', 'public_orders') }}
