# Business Requirements Document: dbt Mesh Cross-Project Lineage POC

## 1. Executive Summary

**Objective:** Demonstrate that dbt Mesh (cross-project lineage) can be achieved using dbt-core without requiring dbt Cloud's $3,000/month enterprise tier.

**Audience:** Senior Data Engineers evaluating cost-effective alternatives to dbt Cloud's mesh capabilities.

---

## 2. Requirements Matrix

| Requirement | Specification |
|-------------|---------------|
| Objective | Enable `dbt_down` projects to reference `dbt_up` models without source code access, preserving full DAG lineage |
| Monorepo Strategy | 3 Projects: `dbt_up` (Source), `dbt_down_loom` (Plugin), `dbt_down` (Native Magic) |
| Registry Management | S3-based manifest storage with `latest/` (contract) and `history/` (audit) partitions |
| Lineage Requirement | Downstream `manifest.json` must contain upstream model `unique_id` in its `parent_map` |
| Governance | Upstream models must explicitly mark `access: public` to be consumable |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        S3 Registry                               │
│  registry/{project}/{env}/latest/manifest.json   (Contract)     │
│  registry/{project}/{env}/history/{ts}/manifest.json (Audit)    │
└─────────────────────────────────────────────────────────────────┘
          ▲                    │                    │
          │ publish            │ dbt-loom          │ state defer
          │                    ▼                    ▼
     ┌─────────┐        ┌──────────────┐     ┌───────────┐
     │ dbt_up  │        │dbt_down_loom │     │ dbt_down  │
     │ (source)│        │  (plugin)    │     │ (native)  │
     └─────────┘        └──────────────┘     └───────────┘
```

---

## 4. Implementation Plan

### 4.1 Directory Structure

```
dbt-mesh-poc/
├── dbt_up/                    # Upstream project (source of truth)
│   ├── models/
│   │   ├── public_orders.sql
│   │   └── schema.yml
│   ├── publish_manifest.py    # CI/CD manifest publisher
│   └── dbt_project.yml
├── dbt_down_loom/             # Downstream using dbt-loom plugin
│   ├── models/
│   │   └── downstream_orders.sql
│   ├── dbt_loom.config.yml
│   └── dbt_project.yml
├── dbt_down/                  # Downstream using native state deferral
│   ├── models/
│   │   └── downstream_orders.sql
│   ├── scripts/
│   │   └── sync_mesh.py
│   ├── state/                 # Downloaded upstream manifests
│   └── dbt_project.yml
├── registry/                  # Local S3 simulation (for testing)
└── validate_lineage.py        # POC validation script
```

### 4.2 Upstream Project (`dbt_up`)

**Purpose:** Define public models with enforced contracts for mesh consumption.

**Files to create:**

1. `dbt_up/dbt_project.yml`
2. `dbt_up/models/public_orders.sql` - Simple staging model
3. `dbt_up/models/schema.yml` - Model config with `access: public` and contract enforcement
4. `dbt_up/publish_manifest.py` - S3 publisher script for CI/CD

**Key Configuration (schema.yml):**
```yaml
version: 2
models:
  - name: public_orders
    access: public
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: integer
```

### 4.3 Downstream Loom Project (`dbt_down_loom`)

**Purpose:** Demonstrate cross-project refs using dbt-loom plugin.

**Files to create:**

1. `dbt_down_loom/dbt_project.yml`
2. `dbt_down_loom/dbt_loom.config.yml` - S3 manifest source configuration
3. `dbt_down_loom/models/downstream_orders.sql` - Model using `{{ ref('dbt_up', 'public_orders') }}`

**Key Configuration (dbt_loom.config.yml):**
```yaml
manifests:
  - name: dbt_up
    type: s3
    config:
      bucket_name: your-poc-bucket
      object_name: registry/dbt_up/prod/latest/manifest.json
```

### 4.4 Downstream Native Project (`dbt_down`)

**Purpose:** Demonstrate cross-project refs using native dbt state deferral.

**Files to create:**

1. `dbt_down/dbt_project.yml`
2. `dbt_down/scripts/sync_mesh.py` - Downloads upstream manifest to `state/` folder
3. `dbt_down/models/downstream_orders.sql` - Model referencing upstream

**Execution Pattern:**
```bash
python scripts/sync_mesh.py
dbt compile --state state/dbt_up --defer
```

### 4.5 Validation Script

**Purpose:** Programmatically verify cross-project lineage exists in compiled manifests.

**File:** `validate_lineage.py`

**Success Criteria:**
- Exit code 0: `parent_map` contains `model.dbt_up.*` references
- Exit code 1: Lineage is broken

---

## 5. Critical Files to Modify/Create

| File | Purpose |
|------|---------|
| `dbt_up/models/schema.yml` | Public model contract definition |
| `dbt_up/publish_manifest.py` | S3 registry publisher |
| `dbt_down_loom/dbt_loom.config.yml` | Plugin manifest source |
| `dbt_down/scripts/sync_mesh.py` | Native state sync script |
| `validate_lineage.py` | POC success validator |

---

## 6. Verification Plan

1. **Build upstream:** `cd dbt_up && dbt build`
2. **Publish manifest:** `python publish_manifest.py`
3. **Build loom downstream:** `cd dbt_down_loom && dbt build`
4. **Build native downstream:** `cd dbt_down && python scripts/sync_mesh.py && dbt compile --state state/dbt_up --defer`
5. **Validate lineage:** `python validate_lineage.py` (must exit 0)

---

## 7. Magic Explained

| Approach | How It Works |
|----------|--------------|
| **dbt-loom** | Python plugin that hacks dbt's internal manifest object in memory during the parse task |
| **Native State Deferral** | `--state` flag tells dbt: "If you don't find this model locally, look for its metadata in this JSON file" |

---

## 8. Dependencies

- dbt-core >= 1.5.0 (for `access` property support)
- dbt-loom (for plugin approach)
- boto3 (for S3 interactions)
- Python 3.9+

---

## 9. Out of Scope

- Production CI/CD pipeline implementation
- Multi-environment (dev/staging/prod) manifest routing
- Automated contract version compatibility checks
