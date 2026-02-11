-- ============================================================================
-- Snowflake Roles and Users Setup for dbt Mesh
-- ============================================================================
-- Creates functional roles for each dbt project and a CI/CD service account
--
-- Run this as ACCOUNTADMIN
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- ============================================================================
-- 1. Create Functional Roles
-- ============================================================================

-- Role for upstream project (dbt_up)
CREATE ROLE IF NOT EXISTS DBT_UP_ROLE
  COMMENT = 'Role for dbt_up project - can write to DBT_UP_PROD and expose public models';

-- Role for downstream project (dbt_down native)
CREATE ROLE IF NOT EXISTS DBT_DOWN_ROLE
  COMMENT = 'Role for dbt_down project - can read from DBT_UP_PROD and write to DBT_DOWN_PROD';

-- Role for downstream project (dbt_down loom)
CREATE ROLE IF NOT EXISTS DBT_DOWN_LOOM_ROLE
  COMMENT = 'Role for dbt_down_loom project - can read from DBT_UP_PROD and write to DBT_DOWN_LOOM_PROD';

-- ============================================================================
-- 2. Grant Warehouse Privileges
-- ============================================================================

-- dbt_up can use its warehouse
GRANT USAGE ON WAREHOUSE DBT_UP_WH TO ROLE DBT_UP_ROLE;
GRANT OPERATE ON WAREHOUSE DBT_UP_WH TO ROLE DBT_UP_ROLE;

-- dbt_down can use its warehouse
GRANT USAGE ON WAREHOUSE DBT_DOWN_WH TO ROLE DBT_DOWN_ROLE;
GRANT OPERATE ON WAREHOUSE DBT_DOWN_WH TO ROLE DBT_DOWN_ROLE;

-- dbt_down_loom can use the downstream warehouse
GRANT USAGE ON WAREHOUSE DBT_DOWN_WH TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT OPERATE ON WAREHOUSE DBT_DOWN_WH TO ROLE DBT_DOWN_LOOM_ROLE;

-- ============================================================================
-- 3. Grant Database Privileges - DBT_UP_ROLE (Upstream)
-- ============================================================================

-- dbt_up owns its database
GRANT USAGE ON DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;
GRANT CREATE SCHEMA ON DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;

-- Full control over schemas
GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;
GRANT CREATE TABLE ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;
GRANT CREATE VIEW ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;

-- Ownership of future objects
GRANT OWNERSHIP ON ALL TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;
GRANT OWNERSHIP ON ALL VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;

-- Future grants (ensures new objects are owned by the role)
GRANT ALL ON FUTURE TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;
GRANT ALL ON FUTURE VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_UP_ROLE;

-- ============================================================================
-- 4. Grant Database Privileges - DBT_DOWN_ROLE (Downstream Native)
-- ============================================================================

-- dbt_down owns its database
GRANT USAGE ON DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;
GRANT CREATE SCHEMA ON DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;

GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;
GRANT CREATE TABLE ON ALL SCHEMAS IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;
GRANT CREATE VIEW ON ALL SCHEMAS IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;

GRANT OWNERSHIP ON ALL TABLES IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;
GRANT OWNERSHIP ON ALL VIEWS IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;

GRANT ALL ON FUTURE TABLES IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;
GRANT ALL ON FUTURE VIEWS IN DATABASE DBT_DOWN_PROD TO ROLE DBT_DOWN_ROLE;

-- READ access to upstream database (for mesh cross-project references)
GRANT USAGE ON DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON ALL TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON ALL VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON FUTURE TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;
GRANT SELECT ON FUTURE VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_ROLE;

-- ============================================================================
-- 5. Grant Database Privileges - DBT_DOWN_LOOM_ROLE (Downstream Loom)
-- ============================================================================

-- dbt_down_loom owns its database
GRANT USAGE ON DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT CREATE SCHEMA ON DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;

GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT CREATE TABLE ON ALL SCHEMAS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT CREATE VIEW ON ALL SCHEMAS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;

GRANT OWNERSHIP ON ALL TABLES IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT OWNERSHIP ON ALL VIEWS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;

GRANT ALL ON FUTURE TABLES IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT ALL ON FUTURE VIEWS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE DBT_DOWN_LOOM_ROLE;

-- READ access to upstream database
GRANT USAGE ON DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON ALL TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON ALL VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON FUTURE TABLES IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;
GRANT SELECT ON FUTURE VIEWS IN DATABASE DBT_UP_PROD TO ROLE DBT_DOWN_LOOM_ROLE;

-- ============================================================================
-- 6. Grant Roles to Your User (for manual testing)
-- ============================================================================

-- Grant all roles to your admin user
GRANT ROLE DBT_UP_ROLE TO USER KHANHLN;
GRANT ROLE DBT_DOWN_ROLE TO USER KHANHLN;
GRANT ROLE DBT_DOWN_LOOM_ROLE TO USER KHANHLN;

-- Allow your user to switch between roles
GRANT ROLE DBT_UP_ROLE TO ROLE ACCOUNTADMIN;
GRANT ROLE DBT_DOWN_ROLE TO ROLE ACCOUNTADMIN;
GRANT ROLE DBT_DOWN_LOOM_ROLE TO ROLE ACCOUNTADMIN;

-- ============================================================================
-- 7. Create CI/CD Service Account (Optional but Recommended)
-- ============================================================================

-- Uncomment if you want a dedicated service account for CI/CD
/*
CREATE USER IF NOT EXISTS DBT_CI_USER
  PASSWORD = 'CHANGE_ME_STRONG_PASSWORD_HERE'
  DEFAULT_ROLE = DBT_UP_ROLE
  DEFAULT_WAREHOUSE = DBT_UP_WH
  MUST_CHANGE_PASSWORD = FALSE
  COMMENT = 'Service account for GitHub Actions CI/CD';

-- Grant all dbt roles to CI user
GRANT ROLE DBT_UP_ROLE TO USER DBT_CI_USER;
GRANT ROLE DBT_DOWN_ROLE TO USER DBT_CI_USER;
GRANT ROLE DBT_DOWN_LOOM_ROLE TO USER DBT_CI_USER;
*/

-- ============================================================================
-- Summary
-- ============================================================================

SHOW ROLES LIKE 'DBT_%';

SELECT
    'Roles created successfully!' AS status,
    'Run 03_create_sample_data.sql next to populate test data' AS next_step;
