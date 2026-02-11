{{
    config(
        materialized='view'
    )
}}

-- Staging model: Clean and type raw customers
SELECT
    customer_id,
    customer_name AS name,
    email,
    signup_date,
    customer_segment AS segment
FROM {{ source('raw', 'raw_customers') }}
