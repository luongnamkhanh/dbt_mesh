# Quick Start Guide - Snowflake dbt Mesh Setup

This guide walks you through setting up and testing the dbt mesh architecture on Snowflake.

## Step 1: Setup Snowflake (5-10 minutes)

### Option A: Using SnowSQL CLI

```bash
# Install SnowSQL if you haven't
# https://docs.snowflake.com/en/user-guide/snowsql-install-config

# Run setup scripts
snowsql -a QMVBJWG-PM06063 -u KHANHLN <<EOF
!source 01_create_databases_and_warehouses.sql
!source 02_create_roles_and_users.sql
!source 03_create_sample_data.sql
EOF
```

### Option B: Using Snowsight Web UI

1. Go to: https://app.snowflake.com/QMVBJWG/PM06063
2. Login with user `KHANHLN`
3. Open each SQL script and run in order:
   - `01_create_databases_and_warehouses.sql`
   - `02_create_roles_and_users.sql`
   - `03_create_sample_data.sql`

### Verify Setup

```sql
-- Check everything is created
SHOW WAREHOUSES LIKE 'DBT_%';
SHOW DATABASES LIKE 'DBT_%';
SHOW ROLES LIKE 'DBT_%';

-- Check sample data
USE DATABASE DBT_UP_PROD;
USE SCHEMA RAW;
SELECT * FROM RAW_ORDERS;
```

## Step 2: Configure dbt Profiles (2 minutes)

```bash
# Set your Snowflake password as environment variable
export DBT_SNOWFLAKE_PASSWORD='your_password_here'

# Copy profiles to dbt config directory
cp snowflake_setup/profiles.yml ~/.dbt/profiles.yml

# Test connection
cd dbt_up
dbt debug
```

You should see: `All checks passed!`

## Step 3: Update dbt Project Configurations

You need to update each project's `dbt_project.yml` to use Snowflake instead of DuckDB.

### Update dbt_up/dbt_project.yml

```yaml
name: dbt_up
version: '1.0.0'
config-version: 2

profile: dbt_up

model-paths: ["models"]

models:
  dbt_up:
    staging:
      +schema: staging
      +materialized: view
    marts:
      +schema: marts
      +materialized: table
```

### Update dbt_down/dbt_project.yml

```yaml
name: dbt_down
version: '1.0.0'
config-version: 2

profile: dbt_down

model-paths: ["models"]

models:
  dbt_down:
    staging:
      +schema: staging
      +materialized: view
    marts:
      +schema: marts
      +materialized: table
```

## Step 4: Create Source Definitions

### For dbt_up - Create `models/sources.yml`

```yaml
version: 2

sources:
  - name: raw
    database: dbt_up_prod
    schema: raw
    tables:
      - name: raw_orders
        columns:
          - name: order_id
          - name: customer_id
          - name: order_status
          - name: order_amount
          - name: order_date
          - name: created_at

      - name: raw_customers
        columns:
          - name: customer_id
          - name: customer_name
          - name: email
          - name: signup_date
          - name: customer_segment
```

### For dbt_up - Create staging model `models/staging/stg_orders.sql`

```sql
{{
    config(
        materialized='view'
    )
}}

SELECT
    order_id,
    customer_id,
    order_status AS status,
    order_amount AS amount,
    order_date,
    created_at
FROM {{ source('raw', 'raw_orders') }}
```

### For dbt_up - Update `models/marts/public_orders.sql`

```sql
{{
    config(
        materialized='table',
        access='public'  -- This makes it available for mesh
    )
}}

SELECT
    order_id,
    status,
    amount,
    created_at
FROM {{ ref('stg_orders') }}
WHERE status IN ('COMPLETED', 'SHIPPED', 'PENDING')
```

## Step 5: Run Upstream Project (dbt_up)

```bash
cd dbt_up

# Build all models
dbt build

# Verify output
dbt show --select public_orders
```

Expected output: Successfully created tables in `DBT_UP_PROD.MARTS`

## Step 6: Update Downstream sync_mesh.py Script

The current script needs a small update to work with Snowflake. The source config should specify the upstream database:

### Update `dbt_down/models/_mesh_dbt_up.yml` manually (or update sync script)

```yaml
version: 2

sources:
  - name: dbt_up
    description: "Public models from upstream dbt_up project (mesh source)"
    database: DBT_UP_PROD    # ← Uppercase for Snowflake
    schema: MARTS             # ← Uppercase for Snowflake
    tables:
      - name: PUBLIC_ORDERS  # ← Uppercase for Snowflake
        description: "Public orders model exposed for cross-project consumption"
        identifier: PUBLIC_ORDERS  # Add this if needed
```

## Step 7: Run Downstream Project (dbt_down)

```bash
cd dbt_down

# Sync upstream manifest (if using mesh sync script)
python3 scripts/sync_mesh.py --bucket $DBT_MESH_BUCKET --env prod --upstream dbt_up

# Or manually create the source file above

# Build with defer (reuses upstream models)
dbt build --defer --state ../dbt_up/target

# Verify lineage
dbt docs generate
dbt docs serve
```

## Step 8: Verify Mesh in Snowflake

```sql
-- Check upstream tables exist
USE ROLE DBT_UP_ROLE;
USE DATABASE DBT_UP_PROD;
USE SCHEMA MARTS;
SHOW TABLES;
SELECT * FROM PUBLIC_ORDERS;

-- Check downstream can read upstream
USE ROLE DBT_DOWN_ROLE;
SELECT * FROM DBT_UP_PROD.MARTS.PUBLIC_ORDERS;  -- Should work!

-- Check downstream tables
USE DATABASE DBT_DOWN_PROD;
USE SCHEMA MARTS;
SHOW TABLES;
SELECT * FROM DOWNSTREAM_ORDERS;
```

## Step 9: Update GitHub Actions Workflows

Update `.github/workflows/downstream-native.yml`:

```yaml
- name: Configure dbt profiles
  run: |
    mkdir -p ~/.dbt
    cat > ~/.dbt/profiles.yml <<EOF
    dbt_down:
      target: prod
      outputs:
        prod:
          type: snowflake
          account: QMVBJWG-PM06063
          user: \${{ secrets.SNOWFLAKE_USER }}
          password: \${{ secrets.SNOWFLAKE_PASSWORD }}
          role: DBT_DOWN_ROLE
          warehouse: DBT_DOWN_WH
          database: DBT_DOWN_PROD
          schema: STAGING
          threads: 4
    EOF
```

Add GitHub Secrets:
- `SNOWFLAKE_USER`: Your username or CI service account
- `SNOWFLAKE_PASSWORD`: Password

## Troubleshooting

### Issue: "Database does not exist"
```bash
# Verify databases were created
snowsql -a QMVBJWG-PM06063 -u KHANHLN -q "SHOW DATABASES LIKE 'DBT_%'"
```

### Issue: "Insufficient privileges"
```sql
-- Check role grants
USE ROLE ACCOUNTADMIN;
SHOW GRANTS TO ROLE DBT_UP_ROLE;
SHOW GRANTS TO ROLE DBT_DOWN_ROLE;
```

### Issue: "002003 (42S02): SQL compilation error: Object does not exist"
- Check case sensitivity - Snowflake uses UPPERCASE by default
- Update source definitions to use uppercase names
- Or use `quoted_identifier: true` in profiles.yml

### Issue: dbt can't find upstream models with --defer
```bash
# Ensure upstream manifest exists
ls -la ../dbt_up/target/manifest.json

# Try running without --defer first to debug
dbt build
```

## What's Next?

1. **Add more models** to test complex lineage
2. **Set up CI/CD** with GitHub Actions
3. **Configure dbt-loom** for the alternative approach
4. **Add tests and documentation** to your models
5. **Set up dbt Cloud** for hosted docs and scheduling

## Clean Up (Optional)

To remove everything and start over:

```sql
USE ROLE ACCOUNTADMIN;

-- Drop databases
DROP DATABASE IF EXISTS DBT_UP_PROD;
DROP DATABASE IF EXISTS DBT_DOWN_PROD;
DROP DATABASE IF EXISTS DBT_DOWN_LOOM_PROD;

-- Drop warehouses
DROP WAREHOUSE IF EXISTS DBT_UP_WH;
DROP WAREHOUSE IF EXISTS DBT_DOWN_WH;

-- Drop roles
DROP ROLE IF EXISTS DBT_UP_ROLE;
DROP ROLE IF EXISTS DBT_DOWN_ROLE;
DROP ROLE IF EXISTS DBT_DOWN_LOOM_ROLE;
```
