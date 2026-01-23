{{
    config(
        materialized='table'
    )
}}

-- Simple staging model representing upstream public orders
-- In production, this would SELECT from a source table

SELECT
    1 AS order_id,
    'PENDING' AS status,
    CAST(100.00 AS DECIMAL(18,3)) AS amount,
    CURRENT_TIMESTAMP AS created_at

UNION ALL

SELECT
    2 AS order_id,
    'COMPLETED' AS status,
    CAST(250.50 AS DECIMAL(18,3)) AS amount,
    CURRENT_TIMESTAMP AS created_at

UNION ALL

SELECT
    3 AS order_id,
    'SHIPPED' AS status,
    CAST(75.25 AS DECIMAL(18,3)) AS amount,
    CURRENT_TIMESTAMP AS created_at
