-- ============================================================================
-- Snowflake Setup for dbt Mesh Demo
-- ============================================================================
-- This script creates the foundational infrastructure for a dbt mesh setup
-- with upstream (dbt_up) and downstream (dbt_down, dbt_down_loom) projects
--
-- Run this as ACCOUNTADMIN
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- ============================================================================
-- 1. Create Warehouses
-- ============================================================================

-- Warehouse for upstream project (dbt_up)
CREATE WAREHOUSE IF NOT EXISTS DBT_UP_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse for dbt_up upstream project';

-- Warehouse for downstream projects (shared by dbt_down and dbt_down_loom)
CREATE WAREHOUSE IF NOT EXISTS DBT_DOWN_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse for dbt_down downstream projects';

-- ============================================================================
-- 2. Create Databases
-- ============================================================================

-- Upstream project database
CREATE DATABASE IF NOT EXISTS DBT_UP_PROD
  COMMENT = 'Production database for dbt_up upstream project';

-- Downstream project database (native mesh approach)
CREATE DATABASE IF NOT EXISTS DBT_DOWN_PROD
  COMMENT = 'Production database for dbt_down downstream project (native mesh)';

-- Downstream project database (loom approach)
CREATE DATABASE IF NOT EXISTS DBT_DOWN_LOOM_PROD
  COMMENT = 'Production database for dbt_down_loom downstream project (dbt-loom)';

-- ============================================================================
-- 3. Create Schemas
-- ============================================================================

-- Upstream schemas
CREATE SCHEMA IF NOT EXISTS DBT_UP_PROD.STAGING
  COMMENT = 'Staging models for dbt_up';

CREATE SCHEMA IF NOT EXISTS DBT_UP_PROD.MARTS
  COMMENT = 'Mart models for dbt_up (includes public models)';

-- Downstream (native) schemas
CREATE SCHEMA IF NOT EXISTS DBT_DOWN_PROD.STAGING
  COMMENT = 'Staging models for dbt_down';

CREATE SCHEMA IF NOT EXISTS DBT_DOWN_PROD.MARTS
  COMMENT = 'Mart models for dbt_down';

-- Downstream (loom) schemas
CREATE SCHEMA IF NOT EXISTS DBT_DOWN_LOOM_PROD.STAGING
  COMMENT = 'Staging models for dbt_down_loom';

CREATE SCHEMA IF NOT EXISTS DBT_DOWN_LOOM_PROD.MARTS
  COMMENT = 'Mart models for dbt_down_loom';

-- ============================================================================
-- 4. Grant Usage to PUBLIC (for easy initial access)
-- ============================================================================

GRANT USAGE ON WAREHOUSE DBT_UP_WH TO ROLE PUBLIC;
GRANT USAGE ON WAREHOUSE DBT_DOWN_WH TO ROLE PUBLIC;

GRANT USAGE ON DATABASE DBT_UP_PROD TO ROLE PUBLIC;
GRANT USAGE ON DATABASE DBT_DOWN_PROD TO ROLE PUBLIC;
GRANT USAGE ON DATABASE DBT_DOWN_LOOM_PROD TO ROLE PUBLIC;

GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_UP_PROD TO ROLE PUBLIC;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_DOWN_PROD TO ROLE PUBLIC;
GRANT USAGE ON ALL SCHEMAS IN DATABASE DBT_DOWN_LOOM_PROD TO ROLE PUBLIC;

-- ============================================================================
-- Summary
-- ============================================================================

SHOW WAREHOUSES LIKE 'DBT_%';
SHOW DATABASES LIKE 'DBT_%';

SELECT
    'Setup complete!' AS status,
    'Run 02_create_roles_and_users.sql next' AS next_step;
