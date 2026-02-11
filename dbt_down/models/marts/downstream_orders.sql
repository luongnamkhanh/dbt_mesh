{{
    config(
        materialized='table'
    )
}}

-- Downstream model that references the upstream public_orders model
-- Using native dbt source() for cross-project reference resolution
--
-- The sync_mesh.py script generates models/_mesh_dbt_up.yml which defines
-- upstream public models as sources in this project.
--
-- This preserves lineage: downstream manifest shows source.dbt_down.dbt_up.public_orders

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
    'dbt_down' AS processed_by
FROM {{ source('dbt_up', 'public_orders') }}
