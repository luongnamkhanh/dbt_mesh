{{
    config(
        materialized='table'
    )
}}

-- Public orders model exposed for cross-project consumption (dbt mesh)
-- Filters for completed, shipped, and pending orders only

SELECT
    order_id,
    status,
    amount,
    created_at
FROM {{ ref('stg_orders') }}
WHERE status IN ('COMPLETED', 'SHIPPED', 'PENDING')
