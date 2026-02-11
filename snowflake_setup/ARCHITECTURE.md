# dbt Mesh Architecture on Snowflake

This document explains the architecture and data flow of the dbt mesh setup.

## Overview

This setup demonstrates **cross-project model dependencies** using dbt mesh with Snowflake as the persistent data warehouse.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Snowflake Account                             │
│            QMVBJWG-PM06063.snowflakecomputing.com               │
└─────────────────────────────────────────────────────────────────┘
                                |
                ┌───────────────┴───────────────┐
                |                               |
         DBT_UP_WH (Compute)          DBT_DOWN_WH (Compute)
         XSMALL, auto-suspend         XSMALL, auto-suspend
                |                               |
                |                               |
    ┌───────────┴───────────┐         ┌────────┴─────────┐
    |                       |         |                  |
DBT_UP_PROD            DBT_DOWN_PROD              DBT_DOWN_LOOM_PROD
(Upstream)             (Downstream Native)        (Downstream dbt-loom)
    |                       |                            |
    ├── RAW                 ├── STAGING                  ├── STAGING
    ├── STAGING             └── MARTS                    └── MARTS
    └── MARTS                    |                           |
         |                       └──────reads from───────────┘
         └────────────reads public models from here──────────┘
```

## Projects

### 1. Upstream Project (dbt_up)

**Purpose**: Owns and publishes core data models

**Database**: `DBT_UP_PROD`
**Warehouse**: `DBT_UP_WH`
**Role**: `DBT_UP_ROLE`

**Schemas**:
- `RAW` - Source data (orders, customers)
- `STAGING` - Cleaned and typed models
- `MARTS` - Business logic and aggregations
  - Contains `access: public` models exposed to downstream

**Key Files**:
- `models/marts/public_orders.sql` - Marked as `access: public`
- `dbt_project.yml` - Profile: `dbt_up`

**Build Command**:
```bash
cd dbt_up
dbt build --target prod
```

**Output**: Tables in `DBT_UP_PROD.MARTS.PUBLIC_ORDERS`

---

### 2. Downstream Project - Native Mesh (dbt_down)

**Purpose**: Consumes upstream models using native dbt mesh + sources

**Database**: `DBT_DOWN_PROD`
**Warehouse**: `DBT_DOWN_WH`
**Role**: `DBT_DOWN_ROLE`

**Schemas**:
- `STAGING` - Staging models
- `MARTS` - Downstream business logic

**Key Files**:
- `models/_mesh_dbt_up.yml` - Source definition pointing to upstream
- `models/downstream_orders.sql` - Uses `{{ source('dbt_up', 'public_orders') }}`
- `scripts/sync_mesh.py` - Syncs upstream manifest from S3

**Build Command**:
```bash
cd dbt_down
python3 scripts/sync_mesh.py --bucket $DBT_MESH_BUCKET --env prod --upstream dbt_up
dbt build --defer --state ../dbt_up/target --target prod
```

**How it Works**:
1. `sync_mesh.py` downloads upstream manifest from S3
2. Generates `_mesh_dbt_up.yml` with source definitions
3. `dbt build --defer` skips rebuilding upstream models
4. Reads directly from `DBT_UP_PROD.MARTS.PUBLIC_ORDERS`

---

### 3. Downstream Project - dbt-loom (dbt_down_loom)

**Purpose**: Consumes upstream models using dbt-loom package

**Database**: `DBT_DOWN_LOOM_PROD`
**Warehouse**: `DBT_DOWN_WH`
**Role**: `DBT_DOWN_LOOM_ROLE`

**Key Files**:
- `packages.yml` - Includes dbt-loom package
- `dependencies.yml` - Declares upstream dependency
- Models use special dbt-loom macros

**Build Command**:
```bash
cd dbt_down_loom
dbt build --target prod
```

**How it Works**:
- dbt-loom automatically resolves cross-project references
- No manual source generation needed
- Uses manifest-based resolution

---

## Data Flow

### End-to-End Flow

```
┌─────────────┐
│  Raw Data   │
│  (S3, APIs) │
└─────┬───────┘
      |
      v
┌──────────────────┐
│   DBT_UP_PROD    │
│   RAW schema     │  ← Loaded by dbt seed or ELT tool
└─────┬────────────┘
      |
      v  dbt_up models
┌──────────────────┐
│   DBT_UP_PROD    │
│ STAGING schema   │  ← ref('stg_orders')
└─────┬────────────┘
      |
      v  dbt_up models
┌──────────────────┐
│   DBT_UP_PROD    │
│  MARTS schema    │  ← public_orders (access: public)
└─────┬────────────┘
      |
      |  Mesh boundary (cross-project reference)
      |
      ├────────────────┬────────────────┐
      |                |                |
      v                v                v
┌───────────┐   ┌───────────┐   ┌────────────┐
│ dbt_down  │   │ dbt_down  │   │  Other     │
│  native   │   │   loom    │   │  Projects  │
└───────────┘   └───────────┘   └────────────┘
```

### CI/CD Flow

#### Upstream CI (dbt_up)
```
1. Git push to upstream/dbt_up branch
2. GitHub Actions triggers
3. Build models: dbt build
4. Publish manifest to S3: python3 publish_manifest.py
5. S3: s3://bucket/registry/dbt_up/prod/latest/manifest.json
```

#### Downstream CI (dbt_down)
```
1. Git push to main branch
2. GitHub Actions triggers
3. Download upstream manifest: python3 sync_mesh.py
4. Generate source definitions: models/_mesh_dbt_up.yml
5. Build with defer: dbt build --defer --state state/dbt_up
   → Reads from DBT_UP_PROD.MARTS.PUBLIC_ORDERS (already exists!)
   → Writes to DBT_DOWN_PROD.MARTS
```

---

## Access Control Matrix

| Role | Database | Permissions | Purpose |
|------|----------|-------------|---------|
| `DBT_UP_ROLE` | `DBT_UP_PROD` | Full (CREATE, SELECT, INSERT, UPDATE, DELETE) | Build upstream models |
| `DBT_DOWN_ROLE` | `DBT_DOWN_PROD` | Full | Build downstream models |
| `DBT_DOWN_ROLE` | `DBT_UP_PROD` | Read-only (SELECT) | Read upstream public models |
| `DBT_DOWN_LOOM_ROLE` | `DBT_DOWN_LOOM_PROD` | Full | Build downstream models |
| `DBT_DOWN_LOOM_ROLE` | `DBT_UP_PROD` | Read-only (SELECT) | Read upstream public models |

---

## Lineage

### Without Mesh (Single Project)
```
source.project.raw.orders
  → model.project.stg_orders
    → model.project.public_orders
      → model.project.downstream_orders
```

### With Native Mesh (Cross-Project)
```
source.dbt_up.raw.orders
  → model.dbt_up.stg_orders
    → model.dbt_up.public_orders (access: public)
      → source.dbt_down.dbt_up.public_orders (mesh boundary)
        → model.dbt_down.downstream_orders
```

**Key Benefits**:
- Shows cross-project dependencies
- Identifies breaking change impact across teams
- Documents data contracts via `access: public`

---

## Why Snowflake vs DuckDB?

| Aspect | DuckDB (File-based) | Snowflake (Cloud Warehouse) |
|--------|---------------------|------------------------------|
| **Persistence** | No - file lost between CI runs | Yes - tables persist |
| **--defer** | Doesn't work (tables missing) | Works (tables exist) |
| **Mesh Support** | Requires sharing DB file | Native support |
| **Cost** | Free | ~$2/hour (only when running) |
| **Production Ready** | No | Yes |
| **Best For** | Local dev | Production mesh |

---

## Deployment Patterns

### Pattern 1: Sequential (Safer)
```
1. Deploy upstream (dbt_up)
2. Wait for completion
3. Deploy downstream (dbt_down)
```

### Pattern 2: Independent (Scalable)
```
Upstream schedule: Every hour
Downstream schedule: Every 15 minutes (uses --defer)
```
Downstream reads already-built upstream tables, no rebuild needed.

### Pattern 3: On-Demand
```
1. Manual trigger for upstream
2. Downstream triggered by upstream completion (webhook/GitHub Actions)
```

---

## Cost Optimization

### Warehouse Sizing
- **XSMALL**: Good for < 100 models, ~$2/hour
- Auto-suspend after 60 seconds → minimal cost
- Expected cost: **< $10/month** for demo usage

### Query Optimization
- Use `incremental` materialization for large tables
- Partition by date for better performance
- Use `--defer` to avoid rebuilding upstream models

### Development Best Practices
- Use separate DEV schemas for development
- Production roles only for CI/CD
- Personal dev schemas: `<USER>_DEV`

---

## Troubleshooting

### Issue: Downstream can't read upstream tables
**Cause**: Role permissions missing
**Fix**: Run `02_create_roles_and_users.sql` again

### Issue: --defer doesn't work
**Cause**: Missing manifest.json
**Fix**: Ensure upstream ran successfully and manifest exists in `target/`

### Issue: "Object does not exist"
**Cause**: Case sensitivity (Snowflake defaults to UPPERCASE)
**Fix**: Update source definitions to use UPPERCASE names

---

## Security Best Practices

1. **Key-Pair Authentication** (recommended over password)
   - Run `./setup_keypair_auth.sh`
   - Store private key in GitHub Secrets

2. **Principle of Least Privilege**
   - Downstream roles only have SELECT on upstream
   - No DELETE or DROP permissions

3. **Network Policies**
   - Restrict access by IP (optional)
   - Enable MFA for user accounts

4. **Audit Logging**
   - Monitor ACCOUNTADMIN usage
   - Track cross-database queries

---

## Next Steps

1. **Add More Models** - Test complex DAGs
2. **Implement Tests** - Data quality checks
3. **Set up dbt Cloud** - Hosted docs and scheduling
4. **Configure Alerting** - Slack/email for failures
5. **Add More Downstream Projects** - Scale the mesh

---

## References

- [dbt Mesh Documentation](https://docs.getdbt.com/docs/collaborate/govern/project-dependencies)
- [Snowflake dbt Setup](https://docs.snowflake.com/en/user-guide/ecosystem-dbt)
- [dbt-loom Package](https://github.com/nicholasyager/dbt-loom)
