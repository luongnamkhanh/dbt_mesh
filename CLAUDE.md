# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **dbt Mesh Cross-Project Lineage POC** demonstrating that dbt mesh capabilities can be achieved using dbt-core without dbt Cloud's enterprise tier. It enables downstream projects to reference upstream models without source code access while preserving full DAG lineage.

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

**Three dbt projects:**
- `dbt_up/` - Upstream project with public models (`access: public` + enforced contracts)
- `dbt_down_loom/` - Downstream using dbt-loom plugin for `{{ ref('dbt_up', 'model') }}`
- `dbt_down/` - Downstream using auto-generated sources for `{{ source('dbt_up', 'model') }}`

## Common Commands

### Setup
```bash
pip install -r requirements.txt
cp profiles.yml.example ~/.dbt/profiles.yml
```

### Full Workflow
```bash
# 1. Build and publish upstream
cd dbt_up && dbt build && python3 publish_manifest.py --local

# 2. Build dbt-loom downstream
cd ../dbt_down_loom && dbt build

# 3. Sync and build native downstream
cd ../dbt_down && python3 scripts/sync_mesh.py --local && dbt build

# 4. Validate lineage (exit 0 = success)
cd .. && python3 validate_lineage.py --all
```

### Individual Project Commands
```bash
# Run dbt commands from project directories
dbt build              # Build all models
dbt compile            # Compile without running
dbt run --select model_name  # Run specific model
```

### Validation
```bash
python3 validate_lineage.py --project dbt_down_loom  # Validate single project
python3 validate_lineage.py --project dbt_down
python3 validate_lineage.py --all                     # Validate all downstream projects
python3 validate_lineage.py --manifest path/to/manifest.json  # Validate specific manifest
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `dbt_up/publish_manifest.py` | Publishes manifest to registry (local or S3) |
| `dbt_down/scripts/sync_mesh.py` | Downloads manifest and generates `_mesh_dbt_up.yml` sources file |
| `validate_lineage.py` | Validates cross-project refs exist in `parent_map` |

## Cross-Project Reference Patterns

**dbt-loom approach** (in `dbt_down_loom`):
```sql
SELECT * FROM {{ ref('dbt_up', 'public_orders') }}
```
Results in `parent_map` containing `model.dbt_up.public_orders`

**Native sources approach** (in `dbt_down`):
```sql
SELECT * FROM {{ source('dbt_up', 'public_orders') }}
```
Results in `parent_map` containing `source.dbt_down.dbt_up.public_orders`

## Governance

Upstream models must have `access: public` in schema.yml to be consumable:
```yaml
models:
  - name: public_orders
    access: public
    config:
      contract:
        enforced: true
```

## Registry Structure

```
registry/
  {project}/
    {env}/
      latest/manifest.json      # Current contract (overwritten)
      history/{timestamp}/manifest.json  # Audit trail
```
