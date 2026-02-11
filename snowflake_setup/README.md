# Snowflake Setup for dbt Mesh Demo

This directory contains SQL scripts to set up your Snowflake environment for the dbt mesh demonstration with upstream (`dbt_up`) and downstream (`dbt_down`, `dbt_down_loom`) projects.

## Prerequisites

- Snowflake account access with `ACCOUNTADMIN` role
- Login credentials: `KHANHLN` user
- Account: `QMVBJWG-PM06063.snowflakecomputing.com`

## Setup Steps

### 1. Run SQL Scripts in Order

Connect to Snowflake using your preferred client (SnowSQL, Snowsight UI, or other) and run these scripts in order:

```bash
# Step 1: Create databases, schemas, and warehouses
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 01_create_databases_and_warehouses.sql

# Step 2: Create roles and grant permissions
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 02_create_roles_and_users.sql

# Step 3: Create sample raw data
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 03_create_sample_data.sql
```

Or run them manually through Snowsight UI by copying and pasting each script.

### 2. Verify Setup

After running the scripts, verify your setup:

```sql
-- Check warehouses
SHOW WAREHOUSES LIKE 'DBT_%';

-- Check databases
SHOW DATABASES LIKE 'DBT_%';

-- Check roles
SHOW ROLES LIKE 'DBT_%';

-- Check sample data
USE DATABASE DBT_UP_PROD;
USE SCHEMA RAW;
SELECT * FROM RAW_ORDERS LIMIT 5;
```

## What Gets Created

### Warehouses
- `DBT_UP_WH` - Compute for upstream project (XSMALL, auto-suspend 60s)
- `DBT_DOWN_WH` - Compute for downstream projects (XSMALL, auto-suspend 60s)

### Databases & Schemas
- `DBT_UP_PROD`
  - `RAW` - Source data
  - `STAGING` - Staging models
  - `MARTS` - Mart models (includes public models for mesh)

- `DBT_DOWN_PROD`
  - `STAGING` - Staging models
  - `MARTS` - Mart models

- `DBT_DOWN_LOOM_PROD`
  - `STAGING` - Staging models
  - `MARTS` - Mart models

### Roles
- `DBT_UP_ROLE` - Full access to DBT_UP_PROD
- `DBT_DOWN_ROLE` - Full access to DBT_DOWN_PROD, READ access to DBT_UP_PROD
- `DBT_DOWN_LOOM_ROLE` - Full access to DBT_DOWN_LOOM_PROD, READ access to DBT_UP_PROD

### Sample Data
- `RAW_ORDERS` - 10 sample orders
- `RAW_CUSTOMERS` - 6 sample customers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Snowflake Account                         │
│  QMVBJWG-PM06063.snowflakecomputing.com                     │
└─────────────────────────────────────────────────────────────┘
                            |
        ┌───────────────────┼───────────────────┐
        |                   |                   |
   DBT_UP_PROD         DBT_DOWN_PROD    DBT_DOWN_LOOM_PROD
   (upstream)          (downstream)      (downstream)
        |                   |                   |
    ┌───┴───┐           ┌───┴───┐          ┌───┴───┐
    │ RAW   │           │STAGING│          │STAGING│
    │STAGING│           │ MARTS │          │ MARTS │
    │ MARTS │◄──────────┴───────┴──────────┴───────┘
    └───────┘         (reads public models)
```

## dbt Mesh Flow

1. **Upstream (dbt_up)** builds models in `DBT_UP_PROD.MARTS`
   - Marks certain models as `access: public`
   - These become available to downstream projects

2. **Downstream (dbt_down, dbt_down_loom)** reference upstream models
   - Uses `--defer` flag to avoid rebuilding upstream models
   - Reads from already-built tables in `DBT_UP_PROD.MARTS`
   - Writes to their own databases

## Next Steps

After running these scripts:

1. **Update dbt profiles** - See `../profiles.yml.example` and update with Snowflake credentials
2. **Update dbt_project.yml** - Configure databases/schemas for each project
3. **Update GitHub Actions workflows** - Use Snowflake instead of DuckDB
4. **Test locally** - Run `dbt build` for each project

## Security Notes

- These scripts grant broad permissions for demo purposes
- For production, use more restrictive permissions
- Consider using key-pair authentication instead of passwords
- Implement network policies and MFA
- Create separate roles for CI/CD vs. developer access

## Troubleshooting

### "Insufficient privileges" error
Ensure you're running scripts as `ACCOUNTADMIN` role.

### "Object does not exist" error
Run scripts in order (01 → 02 → 03).

### "Access denied" when dbt runs
Check role grants and future grants in script 02.

## Cost Optimization

- Warehouses auto-suspend after 60 seconds of inactivity
- XSMALL warehouses cost ~$2/hour (only when running)
- Expected cost for demo: < $5/month if used sparingly
- Suspend warehouses manually: `ALTER WAREHOUSE <name> SUSPEND;`
