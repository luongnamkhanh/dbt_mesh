-- ============================================================================
-- Sample Data for dbt Mesh Testing
-- ============================================================================
-- Creates raw source tables that dbt_up will transform
--
-- Run this as ACCOUNTADMIN or DBT_UP_ROLE
-- ============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE DBT_UP_WH;
USE DATABASE DBT_UP_PROD;

-- ============================================================================
-- 1. Create RAW schema for source data
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS RAW
  COMMENT = 'Raw source data for dbt transformation';

USE SCHEMA RAW;

-- ============================================================================
-- 2. Create raw orders table
-- ============================================================================

CREATE OR REPLACE TABLE RAW_ORDERS (
    order_id INTEGER,
    customer_id INTEGER,
    order_status VARCHAR(50),
    order_amount DECIMAL(10,2),
    order_date DATE,
    created_at TIMESTAMP_NTZ
);

-- Insert sample data
INSERT INTO RAW_ORDERS VALUES
    (1, 101, 'COMPLETED', 150.00, '2024-01-15', '2024-01-15 10:30:00'),
    (2, 102, 'PENDING', 75.50, '2024-01-16', '2024-01-16 14:22:00'),
    (3, 103, 'COMPLETED', 220.00, '2024-01-17', '2024-01-17 09:15:00'),
    (4, 101, 'SHIPPED', 95.25, '2024-01-18', '2024-01-18 11:45:00'),
    (5, 104, 'COMPLETED', 310.00, '2024-01-19', '2024-01-19 16:20:00'),
    (6, 102, 'CANCELLED', 50.00, '2024-01-20', '2024-01-20 08:30:00'),
    (7, 105, 'PENDING', 180.75, '2024-01-21', '2024-01-21 13:10:00'),
    (8, 103, 'COMPLETED', 125.00, '2024-01-22', '2024-01-22 10:55:00'),
    (9, 106, 'SHIPPED', 275.50, '2024-01-23', '2024-01-23 15:40:00'),
    (10, 104, 'COMPLETED', 420.00, '2024-01-24', '2024-01-24 12:00:00');

-- ============================================================================
-- 3. Create raw customers table
-- ============================================================================

CREATE OR REPLACE TABLE RAW_CUSTOMERS (
    customer_id INTEGER,
    customer_name VARCHAR(100),
    email VARCHAR(100),
    signup_date DATE,
    customer_segment VARCHAR(50)
);

-- Insert sample data
INSERT INTO RAW_CUSTOMERS VALUES
    (101, 'Alice Johnson', 'alice@example.com', '2023-06-15', 'RETAIL'),
    (102, 'Bob Smith', 'bob@example.com', '2023-08-22', 'WHOLESALE'),
    (103, 'Carol White', 'carol@example.com', '2023-09-10', 'RETAIL'),
    (104, 'David Brown', 'david@example.com', '2023-10-05', 'ENTERPRISE'),
    (105, 'Eve Davis', 'eve@example.com', '2023-11-20', 'RETAIL'),
    (106, 'Frank Miller', 'frank@example.com', '2023-12-01', 'WHOLESALE');

-- ============================================================================
-- 4. Grant access to dbt roles
-- ============================================================================

-- Grant SELECT to all dbt roles (they all need to read raw data)
GRANT USAGE ON SCHEMA RAW TO ROLE DBT_UP_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA RAW TO ROLE DBT_UP_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAW TO ROLE DBT_UP_ROLE;

GRANT USAGE ON SCHEMA RAW TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA RAW TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAW TO ROLE DBT_DOWN_ROLE;

GRANT USAGE ON SCHEMA RAW TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA RAW TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAW TO ROLE DBT_DOWN_LOOM_ROLE;

-- ============================================================================
-- 5. Verify data
-- ============================================================================

SELECT 'RAW_ORDERS' AS table_name, COUNT(*) AS row_count FROM RAW_ORDERS
UNION ALL
SELECT 'RAW_CUSTOMERS', COUNT(*) FROM RAW_CUSTOMERS;

-- Sample queries
SELECT
    'Sample Orders' AS description,
    order_id,
    order_status,
    order_amount
FROM RAW_ORDERS
LIMIT 5;

SELECT
    'Sample Customers' AS description,
    customer_id,
    customer_name,
    customer_segment
FROM RAW_CUSTOMERS
LIMIT 5;

-- ============================================================================
-- Summary
-- ============================================================================

SELECT
    'Sample data created successfully!' AS status,
    'You can now run dbt_up to transform this data' AS next_step,
    'Tables: RAW_ORDERS, RAW_CUSTOMERS' AS tables_created;
