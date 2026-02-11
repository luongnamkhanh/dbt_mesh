# dbt Mesh Cross-Project Lineage POC

> Demonstrating dbt mesh capabilities using dbt-core without dbt Cloud's enterprise tier

[![Upstream CI](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/upstream.yml/badge.svg)](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/upstream.yml)
[![Downstream Loom CI](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/downstream-loom.yml/badge.svg)](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/downstream-loom.yml)
[![Downstream Native CI](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/downstream-native.yml/badge.svg)](https://github.com/luongnamkhanh/dbt_mesh/actions/workflows/downstream-native.yml)

## Overview

This POC demonstrates two approaches for achieving dbt mesh functionality:

1. **dbt-loom plugin**: Cross-project refs via `{{ ref('project', 'model') }}`
2. **Native sources**: Auto-generated sources from upstream manifests

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        S3 Registry                               │
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
```

## Branch Structure

This repository uses separate branches for each project to simulate real-world team autonomy:

- `main` - Documentation and shared utilities
- `upstream/dbt_up` - Upstream project with public models
- `downstream/dbt_down_loom` - Downstream using dbt-loom plugin
- `downstream/dbt_down` - Downstream using native sources

## Quick Start

### Prerequisites

**Database Setup (Snowflake)**

This project uses Snowflake for persistent database storage. See the complete setup guide:

📖 **[Snowflake Setup Guide](dbt_down/snowflake_setup/INDEX.md)**

Quick setup (5-10 minutes):
```bash
# 1. Run Snowflake SQL scripts (in Snowsight or SnowSQL)
cd dbt_down/snowflake_setup
# Run: 01_create_databases_and_warehouses.sql
# Run: 02_create_roles_and_users.sql
# Run: 03_create_sample_data.sql

# 2. Configure dbt profiles
export DBT_SNOWFLAKE_PASSWORD='your_password'
cp dbt_down/snowflake_setup/profiles.yml ~/.dbt/profiles.yml

# 3. Test connection
cd dbt_up && dbt debug
```

**Install Python dependencies**
```bash
pip install -r requirements.txt
```

### Local Testing (Monorepo Mode)

**With Snowflake (Recommended - Full Features)**
```bash
# 1. Build and publish upstream
cd dbt_up
dbt build --target prod
python3 publish_manifest.py --local
cd ..

# 2. Build downstream (loom) - reads from DBT_UP_PROD
cd dbt_down_loom
dbt build --target prod
cd ..

# 3. Build downstream (native) - uses --defer for efficiency
cd dbt_down
python3 scripts/sync_mesh.py --local
dbt build --target prod --defer --state ../dbt_up/target
cd ..

# 4. Validate lineage
python3 validate_lineage.py --all
```

> **Why Snowflake?** Persistent databases enable true `--defer` functionality where downstream projects skip rebuilding upstream models and read directly from `DBT_UP_PROD` tables.

## CI/CD Setup

Each branch has automated CI/CD:

### 1. Configure GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `SNOWFLAKE_ACCOUNT` | Your Snowflake account identifier (e.g., QMVBJWG-PM06063) |
| `SNOWFLAKE_USER` | Snowflake username or CI service account |
| `SNOWFLAKE_PASSWORD` | Snowflake password |
| `AWS_ACCESS_KEY_ID` | Your AWS access key (for S3 manifest registry) |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_SESSION_TOKEN` | Your AWS session token (if using temporary credentials) |

### 2. Update S3 Bucket Name

Edit the `DBT_MESH_BUCKET` environment variable in each workflow file:
- `.github/workflows/upstream.yml`
- `.github/workflows/downstream-loom.yml`
- `.github/workflows/downstream-native.yml`

### 3. Workflow Triggers

**Upstream workflow** (on `upstream/dbt_up` branch):
- Builds dbt models
- Publishes manifest to S3
- Validates public models

**Downstream workflows** (on respective branches):
- Syncs upstream manifest from S3
- Builds dbt models
- Validates cross-project lineage

## Key Concepts

### Public Models

Upstream models must be marked as `public` to be consumable:

```yaml
models:
  - name: public_orders
    access: public
    config:
      contract:
        enforced: true
```

### Cross-Project References

**dbt-loom approach**:
```sql
SELECT * FROM {{ ref('dbt_up', 'public_orders') }}
```

**Native sources approach**:
```sql
SELECT * FROM {{ source('dbt_up', 'public_orders') }}
```

### Registry Structure

```
s3://your-bucket/registry/
  dbt_up/
    prod/
      latest/manifest.json      # Current contract
      history/
        20260123T064541Z/manifest.json  # Audit trail
```

## Governance

- Upstream models require `access: public` declaration
- Contract enforcement validates schema changes
- Manifest versioning in `history/` partition
- Lineage validation in CI/CD pipelines

## Branch Restructuring Guide

See [BRANCHING.md](BRANCHING.md) for instructions on converting the monorepo to separate branches.

## Documentation

- [CLAUDE.md](CLAUDE.md) - Guide for Claude Code
- [plan.md](plan.md) - Original business requirements

## License

MIT
