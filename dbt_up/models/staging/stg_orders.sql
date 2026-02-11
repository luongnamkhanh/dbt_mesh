{{
    config(
        materialized='view'
    )
}}

-- Staging model: Clean and type raw orders
SELECT
    order_id,
    customer_id,
    order_status AS status,
    order_amount AS amount,
    order_date,
    created_at
FROM {{ source('raw', 'raw_orders') }}
