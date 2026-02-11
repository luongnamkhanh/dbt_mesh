-- ============================================================================
-- Verification Script for dbt Mesh Snowflake Setup
-- ============================================================================
-- Run this script to verify all components are properly configured
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- ============================================================================
-- 1. Check Warehouses
-- ============================================================================

SELECT '=== WAREHOUSES ===' AS section;

SHOW WAREHOUSES LIKE 'DBT_%';

SELECT
    "name" AS warehouse_name,
    "size" AS warehouse_size,
    "state" AS current_state,
    "auto_suspend" AS auto_suspend_mins,
    "auto_resume" AS auto_resume_enabled
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================================
-- 2. Check Databases
-- ============================================================================

SELECT '=== DATABASES ===' AS section;

SHOW DATABASES LIKE 'DBT_%';

SELECT
    "name" AS database_name,
    "owner" AS owner_role,
    "comment" AS description
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================================
-- 3. Check Schemas
-- ============================================================================

SELECT '=== SCHEMAS ===' AS section;

-- DBT_UP_PROD schemas
USE DATABASE DBT_UP_PROD;
SHOW SCHEMAS;

SELECT
    'DBT_UP_PROD' AS database_name,
    "name" AS schema_name,
    "owner" AS owner_role
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" IN ('RAW', 'STAGING', 'MARTS');

-- DBT_DOWN_PROD schemas
USE DATABASE DBT_DOWN_PROD;
SHOW SCHEMAS;

SELECT
    'DBT_DOWN_PROD' AS database_name,
    "name" AS schema_name,
    "owner" AS owner_role
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" IN ('STAGING', 'MARTS');

-- DBT_DOWN_LOOM_PROD schemas
USE DATABASE DBT_DOWN_LOOM_PROD;
SHOW SCHEMAS;

SELECT
    'DBT_DOWN_LOOM_PROD' AS database_name,
    "name" AS schema_name,
    "owner" AS owner_role
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" IN ('STAGING', 'MARTS');

-- ============================================================================
-- 4. Check Roles
-- ============================================================================

SELECT '=== ROLES ===' AS section;

SHOW ROLES LIKE 'DBT_%';

SELECT
    "name" AS role_name,
    "comment" AS description,
    "assigned_to_users" AS users_count
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================================
-- 5. Check Sample Data
-- ============================================================================

SELECT '=== SAMPLE DATA ===' AS section;

USE DATABASE DBT_UP_PROD;
USE SCHEMA RAW;

-- Check RAW_ORDERS
SELECT
    'RAW_ORDERS' AS table_name,
    COUNT(*) AS row_count,
    MIN(order_date) AS earliest_order,
    MAX(order_date) AS latest_order
FROM RAW_ORDERS;

-- Check RAW_CUSTOMERS
SELECT
    'RAW_CUSTOMERS' AS table_name,
    COUNT(*) AS row_count,
    COUNT(DISTINCT customer_segment) AS segments_count
FROM RAW_CUSTOMERS;

-- Sample rows
SELECT
    'Sample Orders (first 3)' AS description,
    order_id,
    order_status,
    order_amount,
    order_date
FROM RAW_ORDERS
ORDER BY order_id
LIMIT 3;

-- ============================================================================
-- 6. Check Role Permissions
-- ============================================================================

SELECT '=== ROLE PERMISSIONS ===' AS section;

-- DBT_UP_ROLE permissions on DBT_UP_PROD
USE ROLE ACCOUNTADMIN;
SHOW GRANTS TO ROLE DBT_UP_ROLE;

SELECT
    'DBT_UP_ROLE' AS role_name,
    "privilege" AS privilege,
    "granted_on" AS object_type,
    "name" AS object_name
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" LIKE '%DBT_UP%'
ORDER BY "granted_on", "name";

-- DBT_DOWN_ROLE permissions
SHOW GRANTS TO ROLE DBT_DOWN_ROLE;

SELECT
    'DBT_DOWN_ROLE' AS role_name,
    "privilege" AS privilege,
    "granted_on" AS object_type,
    "name" AS object_name
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" LIKE '%DBT_%'
ORDER BY "granted_on", "name";

-- ============================================================================
-- 7. Test Cross-Database Access
-- ============================================================================

SELECT '=== CROSS-DATABASE ACCESS TEST ===' AS section;

-- Test: Can DBT_DOWN_ROLE read from DBT_UP_PROD?
USE ROLE DBT_DOWN_ROLE;
USE DATABASE DBT_UP_PROD;
USE SCHEMA RAW;

SELECT
    'Cross-database access test' AS test_name,
    CASE
        WHEN COUNT(*) > 0 THEN '✓ PASS - DBT_DOWN_ROLE can read from DBT_UP_PROD.RAW'
        ELSE '✗ FAIL - No access'
    END AS result
FROM RAW_ORDERS;

-- ============================================================================
-- 8. Summary Report
-- ============================================================================

USE ROLE ACCOUNTADMIN;

SELECT '=== SETUP SUMMARY ===' AS section;

WITH setup_check AS (
    SELECT
        1 AS check_order,
        'Warehouses' AS component,
        (SELECT COUNT(*) FROM (SHOW WAREHOUSES LIKE 'DBT_%')) AS expected_count,
        2 AS actual_count,
        (SELECT COUNT(*) FROM (SHOW WAREHOUSES LIKE 'DBT_%')) = 2 AS is_correct
    UNION ALL
    SELECT
        2, 'Databases', 3,
        (SELECT COUNT(*) FROM (SHOW DATABASES LIKE 'DBT_%')),
        (SELECT COUNT(*) FROM (SHOW DATABASES LIKE 'DBT_%')) = 3
    UNION ALL
    SELECT
        3, 'Roles', 3,
        (SELECT COUNT(*) FROM (SHOW ROLES LIKE 'DBT_%')),
        (SELECT COUNT(*) FROM (SHOW ROLES LIKE 'DBT_%')) = 3
    UNION ALL
    SELECT
        4, 'Sample Orders', 10,
        (SELECT COUNT(*) FROM DBT_UP_PROD.RAW.RAW_ORDERS),
        (SELECT COUNT(*) FROM DBT_UP_PROD.RAW.RAW_ORDERS) = 10
    UNION ALL
    SELECT
        5, 'Sample Customers', 6,
        (SELECT COUNT(*) FROM DBT_UP_PROD.RAW.RAW_CUSTOMERS),
        (SELECT COUNT(*) FROM DBT_UP_PROD.RAW.RAW_CUSTOMERS) = 6
)
SELECT
    component,
    expected_count,
    actual_count,
    CASE
        WHEN is_correct THEN '✓ PASS'
        ELSE '✗ FAIL'
    END AS status
FROM setup_check
ORDER BY check_order;

-- Final message
SELECT
    CASE
        WHEN (SELECT COUNT(*) FROM (SHOW DATABASES LIKE 'DBT_%')) = 3
         AND (SELECT COUNT(*) FROM (SHOW WAREHOUSES LIKE 'DBT_%')) = 2
         AND (SELECT COUNT(*) FROM (SHOW ROLES LIKE 'DBT_%')) = 3
         AND (SELECT COUNT(*) FROM DBT_UP_PROD.RAW.RAW_ORDERS) = 10
        THEN '✓✓✓ ALL CHECKS PASSED! Ready to run dbt ✓✓✓'
        ELSE '⚠ Some checks failed. Review output above.'
    END AS final_status;
