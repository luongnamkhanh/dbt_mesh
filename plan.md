# dbt Mesh Cross-Project Lineage POC - Current Implementation

## 1. Executive Summary

**Status:** ✅ Fully Implemented and Operational

**Objective:** Successfully demonstrated that dbt Mesh (cross-project lineage) can be achieved using dbt-core without requiring dbt Cloud's $3,000/month enterprise tier.

**Audience:** Senior Data Engineers evaluating cost-effective alternatives to dbt Cloud's mesh capabilities.

**Implementation Date:** January 2026

---

## 2. Implementation Overview

| Component | Status | Details |
|-----------|--------|---------|
| Objective | ✅ Achieved | Downstream projects (`dbt_down`, `dbt_down_loom`) reference upstream (`dbt_up`) models without source code access, preserving full DAG lineage |
| Project Structure | ✅ Implemented | 3 Projects: `dbt_up` (Upstream), `dbt_down_loom` (dbt-loom Plugin), `dbt_down` (Native Sources) |
| Registry System | ✅ Operational | S3/local manifest storage with `latest/` (contract) and `history/` (audit) partitions |
| Lineage Verification | ✅ Validated | Downstream manifests contain upstream model references in `parent_map` and `depends_on` |
| Governance | ✅ Enforced | Upstream models marked `access: public` with contract enforcement |
| Database | ✅ Snowflake | Persistent databases enable true `--defer` functionality |
| CI/CD | ✅ Automated | GitHub Actions workflows for all three projects |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     S3/Local Registry                            │
│  registry/{project}/{env}/latest/manifest.json   (Contract)     │
│  registry/{project}/{env}/history/{ts}/manifest.json (Audit)    │
└─────────────────────────────────────────────────────────────────┘
          ▲                    │                    │
          │ publish            │ dbt-loom          │ sources
          │                    ▼                    ▼
     ┌─────────┐        ┌──────────────┐     ┌───────────┐
     │ dbt_up  │        │dbt_down_loom │     │ dbt_down  │
     │ (source)│        │  (plugin)    │     │ (native)  │
     └─────────┘        └──────────────┘     └───────────┘
          │                    │                    │
          └────────────────────┴────────────────────┘
                               │
                ┌──────────────┴───────────────┐
                │      Snowflake Cloud         │
                │  DBT_UP_PROD, DBT_DOWN_PROD  │
                │  DBT_DOWN_LOOM_PROD          │
                └──────────────────────────────┘
```

---

## 4. Implemented Directory Structure

```
dbt-mesh-poc/
├── dbt_up/                           # Upstream project (data provider)
│   ├── dbt_project.yml
│   ├── publish_manifest.py           # Manifest publisher to S3/local registry
│   ├── models/
│   │   ├── sources.yml               # Raw data sources (raw_orders, raw_customers)
│   │   ├── staging/
│   │   │   ├── stg_orders.sql        # Staging model (view)
│   │   │   └── stg_customers.sql     # Staging model (view)
│   │   └── marts/
│   │       ├── public_orders.sql     # Public model for mesh consumption (table)
│   │       └── schema.yml            # Model config with access:public + contract
│   └── target/
│       └── manifest.json             # Compiled manifest
│
├── dbt_down_loom/                    # Downstream using dbt-loom plugin
│   ├── dbt_project.yml
│   ├── dbt_loom.config.yml          # Manifest source configuration
│   └── models/
│       └── marts/
│           ├── downstream_orders.sql # Uses {{ ref('dbt_up', 'public_orders') }}
│           └── schema.yml
│
├── dbt_down/                         # Downstream using native sources
│   ├── dbt_project.yml
│   ├── scripts/
│   │   └── sync_mesh.py             # Downloads manifest, generates _mesh_dbt_up.yml
│   └── models/
│       ├── marts/
│       │   ├── downstream_orders.sql # Uses {{ source('dbt_up', 'public_orders') }}
│       │   └── schema.yml
│       └── state/                    # For --defer state storage
│
├── snowflake_setup/                  # Snowflake infrastructure
│   ├── INDEX.md                      # Navigation guide
│   ├── README.md                     # Complete setup documentation
│   ├── QUICKSTART.md                 # Quick start walkthrough
│   ├── ARCHITECTURE.md               # Deep dive into architecture
│   ├── profiles.yml                  # Complete Snowflake profiles
│   ├── setup_keypair_auth.sh         # SSH key setup script
│   ├── 01_create_databases_and_warehouses.sql
│   ├── 02_create_roles_and_users.sql
│   ├── 03_create_sample_data.sql
│   └── 04_verify_setup.sql
│
├── registry/                         # Local manifest registry (S3 simulation)
│   └── dbt_up/
│       └── prod/
│           ├── latest/
│           │   └── manifest.json     # Current contract
│           └── history/
│               └── {timestamp}/
│                   └── manifest.json # Audit trail
│
├── .github/workflows/                # CI/CD automation
│   ├── upstream.yml                  # Builds dbt_up, publishes manifest
│   ├── downstream-loom.yml           # Builds dbt_down_loom
│   ├── downstream-native.yml         # Builds dbt_down with defer
│   └── main-docs.yml                 # Documentation generation
│
├── validate_lineage.py               # Cross-project lineage validator
├── requirements.txt                  # Python dependencies
├── profiles.yml.example              # Example dbt profiles
├── README.md                         # Main documentation
├── CLAUDE.md                         # Claude Code instructions
├── SETUP.md                          # Setup guide
├── QUICKSTART.md                     # Quick start guide
├── BRANCHING.md                      # Branch strategy
└── CI_CD_APPROACHES.md              # CI/CD patterns
```

---

## 5. Upstream Project (`dbt_up`)

**Purpose:** Publishes public models with enforced contracts for mesh consumption.

### Model Structure

```
dbt_up/models/
├── sources.yml           # Defines raw_orders and raw_customers sources
├── staging/
│   ├── stg_orders.sql    # Cleans raw orders (materialized: view)
│   └── stg_customers.sql # Cleans raw customers (materialized: view)
└── marts/
    ├── public_orders.sql # Public model for downstream consumption (materialized: table)
    └── schema.yml        # Model config with access:public + contract enforcement
```

### Key Configuration (schema.yml)

```yaml
version: 2
models:
  - name: public_orders
    description: "Public orders model exposed for cross-project consumption"
    access: public
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        description: "Unique order identifier"
        data_type: integer
        constraints:
          - type: not_null
      - name: status
        description: "Order status (PENDING, COMPLETED, SHIPPED)"
        data_type: varchar
      - name: amount
        description: "Order total amount"
        data_type: "decimal(10,2)"
      - name: created_at
        description: "Order creation timestamp"
        data_type: "timestamp_ntz"
```

### Manifest Publishing

**Script:** `dbt_up/publish_manifest.py`

**Features:**
- Publishes manifest to S3 or local registry
- Creates `latest/` partition (current contract)
- Creates `history/{timestamp}/` partition (audit trail)
- Supports both production (S3) and local development modes

**Usage:**
```bash
# Local registry (for testing)
python3 publish_manifest.py --local

# S3 registry (for production)
python3 publish_manifest.py
```

---

## 6. Downstream Loom Project (`dbt_down_loom`)

**Purpose:** Demonstrates cross-project refs using dbt-loom plugin.

### Configuration (dbt_loom.config.yml)

```yaml
manifests:
  # Local filesystem manifest (for development/testing)
  - name: dbt_up
    type: file
    config:
      path: ../registry/dbt_up/prod/latest/manifest.json

# S3 configuration (for production):
# manifests:
#   - name: dbt_up
#     type: s3
#     config:
#       bucket_name: your-dbt-mesh-bucket
#       object_name: registry/dbt_up/prod/latest/manifest.json
```

### Model Implementation (downstream_orders.sql)

```sql
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
    'dbt_down_loom' AS processed_by
FROM {{ ref('dbt_up', 'public_orders') }}
```

**Lineage:** Shows as `model.dbt_up.public_orders` in `parent_map`

---

## 7. Downstream Native Project (`dbt_down`)

**Purpose:** Demonstrates cross-project refs using native dbt sources with state deferral.

### Sync Script (scripts/sync_mesh.py)

**Features:**
- Downloads upstream manifest from S3 or local registry
- Auto-generates `models/_mesh_dbt_up.yml` with source definitions
- Supports both production (S3) and local development modes

**Usage:**
```bash
# Local registry
python3 scripts/sync_mesh.py --local

# S3 registry
python3 scripts/sync_mesh.py
```

### Model Implementation (downstream_orders.sql)

```sql
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
```

**Lineage:** Shows as `source.dbt_down.dbt_up.public_orders` in `parent_map`

### Execution Pattern with --defer

```bash
# Sync manifest and generate sources
python3 scripts/sync_mesh.py --local

# Build with defer (skips rebuilding upstream models)
dbt build --target prod --defer --state ../dbt_up/target
```

**Benefit:** `--defer` allows downstream to read directly from `DBT_UP_PROD.MARTS.PUBLIC_ORDERS` in Snowflake without rebuilding upstream models, saving compute and time.

---

## 8. Snowflake Infrastructure

### Database & Schema Structure

```
DBT_UP_PROD
├── RAW       ← Source tables (raw_orders, raw_customers)
├── STAGING   ← Staging models (stg_orders, stg_customers)
└── MARTS     ← Public models (public_orders) with access:public

DBT_DOWN_PROD
├── STAGING   ← Downstream staging
└── MARTS     ← Downstream marts (downstream_orders)

DBT_DOWN_LOOM_PROD
├── STAGING   ← Downstream staging (dbt-loom approach)
└── MARTS     ← Downstream marts (downstream_orders)
```

### Setup Scripts

Located in `snowflake_setup/` directory (run in order):

1. **`01_create_databases_and_warehouses.sql`**
   - Creates 3 databases with 7 schemas
   - Creates 2 warehouses (DEV_WH, PROD_WH)

2. **`02_create_roles_and_users.sql`**
   - Creates 3 roles (DBT_UP_ROLE, DBT_DOWN_ROLE, DBT_DOWN_LOOM_ROLE)
   - Grants cross-database read permissions for mesh
   - Creates users with appropriate roles

3. **`03_create_sample_data.sql`**
   - Loads 10 sample orders
   - Loads 6 sample customers

4. **`04_verify_setup.sql`**
   - Verification checks for all components

**Setup Time:** 5-10 minutes

**Documentation:** See `snowflake_setup/INDEX.md` for complete guide

---

## 9. Validation Script

**File:** `validate_lineage.py` (root directory)

**Purpose:** Programmatically verifies cross-project lineage exists in compiled manifests.

**Features:**
- Validates both `parent_map` and `depends_on` for upstream references
- Supports validating individual projects or all projects
- Supports validating specific manifest files

**Usage:**
```bash
# Validate single project
python3 validate_lineage.py --project dbt_down_loom
python3 validate_lineage.py --project dbt_down

# Validate all downstream projects
python3 validate_lineage.py --all

# Validate specific manifest
python3 validate_lineage.py --manifest path/to/manifest.json
```

**Success Criteria:**
- Exit code 0: Cross-project lineage verified
- Exit code 1: Lineage is broken or missing

---

## 10. Full Workflow (Local Testing with Snowflake)

### Prerequisites
```bash
# 1. Run Snowflake setup (5-10 minutes)
cd snowflake_setup
# Run SQL scripts: 01, 02, 03

# 2. Install dependencies and configure profiles
pip install -r requirements.txt
export DBT_SNOWFLAKE_PASSWORD='your_password'
cp snowflake_setup/profiles.yml ~/.dbt/profiles.yml
```

### Complete Workflow
```bash
# 1. Build and publish upstream to Snowflake
cd dbt_up
dbt build --target prod
python3 publish_manifest.py --local
cd ..

# 2. Build dbt-loom downstream (reads from DBT_UP_PROD)
cd dbt_down_loom
dbt build --target prod
cd ..

# 3. Sync and build native downstream with defer
cd dbt_down
python3 scripts/sync_mesh.py --local
dbt build --target prod --defer --state ../dbt_up/target
cd ..

# 4. Validate lineage (must exit 0)
python3 validate_lineage.py --all
```

**Expected Output:**
```
✓ dbt_down_loom: Cross-project lineage verified
  - Found reference: model.dbt_up.public_orders
✓ dbt_down: Cross-project lineage verified
  - Found reference: source.dbt_down.dbt_up.public_orders
```

---

## 11. CI/CD Implementation

### GitHub Actions Workflows

Located in `.github/workflows/`:

1. **`upstream.yml`** (on `upstream/dbt_up` branch)
   - Builds dbt models in Snowflake
   - Publishes manifest to S3
   - Validates public models

2. **`downstream-loom.yml`** (on `downstream/dbt_down_loom` branch)
   - Downloads upstream manifest from S3
   - Builds dbt models with dbt-loom
   - Validates cross-project lineage

3. **`downstream-native.yml`** (on `downstream/dbt_down` branch)
   - Downloads upstream manifest from S3
   - Generates sources with sync_mesh.py
   - Builds dbt models with --defer
   - Validates cross-project lineage

4. **`main-docs.yml`**
   - Generates and publishes documentation

### Required GitHub Secrets

| Secret Name | Purpose |
|-------------|---------|
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Snowflake username |
| `SNOWFLAKE_PASSWORD` | Snowflake password |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 |
| `AWS_SESSION_TOKEN` | AWS session token (if using temporary credentials) |

---

## 12. Key Implementation Files

| File | Purpose | Status |
|------|---------|--------|
| `dbt_up/models/marts/schema.yml` | Public model contract definition with `access: public` | ✅ Implemented |
| `dbt_up/publish_manifest.py` | S3/local registry publisher with versioning | ✅ Implemented |
| `dbt_down_loom/dbt_loom.config.yml` | Plugin manifest source configuration | ✅ Implemented |
| `dbt_down/scripts/sync_mesh.py` | Native state sync + source generation | ✅ Implemented |
| `validate_lineage.py` | POC success validator | ✅ Implemented |
| `snowflake_setup/*.sql` | Complete Snowflake infrastructure | ✅ Implemented |
| `.github/workflows/*.yml` | CI/CD automation | ✅ Implemented |

---

## 13. How the Magic Works

| Approach | Mechanism | Lineage Tracking |
|----------|-----------|------------------|
| **dbt-loom** | Python plugin that modifies dbt's internal manifest object in memory during the parse task, injecting upstream model metadata | Shows as `model.dbt_up.public_orders` in `parent_map` |
| **Native Sources** | `{{ source() }}` + `--defer --state` tells dbt: "If you don't find this model locally, look for its metadata in the upstream manifest JSON and read from the physical table in Snowflake" | Shows as `source.dbt_down.dbt_up.public_orders` in `parent_map` |

**Why --defer is powerful:**
- Downstream doesn't rebuild upstream models
- Reads directly from upstream Snowflake tables (`DBT_UP_PROD.MARTS.PUBLIC_ORDERS`)
- Saves compute time and costs
- Requires persistent database (Snowflake, not in-memory DBs)

---

## 14. Dependencies

**Installed and Verified:**
- ✅ dbt-core >= 1.5.0 (for `access` property support)
- ✅ dbt-snowflake >= 1.5.0 (primary database adapter)
- ✅ dbt-loom >= 0.9.0 (for plugin approach)
- ✅ boto3 >= 1.26.0 (for S3 interactions)
- ✅ Python 3.9+

---

## 15. Success Metrics

| Metric | Target | Actual Status |
|--------|--------|---------------|
| Cross-project lineage preservation | ✅ Required | ✅ Verified in both approaches |
| Upstream contract enforcement | ✅ Required | ✅ Enforced via `contract: enforced: true` |
| Downstream autonomy (no source code access) | ✅ Required | ✅ Achieved via manifest registry |
| Manifest versioning | ✅ Required | ✅ Latest + history partitions |
| CI/CD automation | ✅ Required | ✅ GitHub Actions workflows |
| Documentation completeness | ✅ Required | ✅ 8 documentation files |
| Cost savings vs dbt Cloud Enterprise | $3,000/month | ✅ Achieved using dbt-core |

---

## 16. Out of Scope (Future Enhancements)

- Multi-environment (dev/staging/prod) manifest routing with environment-specific configurations
- Automated contract version compatibility checks and breaking change detection
- Manifest schema evolution tracking and migration tools
- Integration with data catalogs (DataHub, Atlan)
- Automated rollback on downstream build failures

---

## 17. Conclusion

**POC Status:** ✅ **Successfully Demonstrated**

This implementation proves that enterprise-grade dbt mesh capabilities can be achieved using:
- dbt-core (open source)
- Standard cloud storage (S3)
- Custom automation scripts (Python)
- GitHub Actions (free tier)

**Total Cost:** ~$0/month (excluding Snowflake compute, which is usage-based)

**vs dbt Cloud Enterprise:** $3,000/month savings

**Production Readiness:** This POC is production-ready and can be deployed to real data pipelines with minimal modifications (primarily S3 bucket configuration and secret management).
