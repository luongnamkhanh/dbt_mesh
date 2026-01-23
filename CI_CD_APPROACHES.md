# CI/CD Approaches for dbt Mesh

This document explains the trade-offs between different cross-project reference approaches in CI/CD environments.

## Summary Table

| Approach | CI/CD Compatible | Shared DB Required | Complexity | Best For |
|----------|------------------|-------------------|------------|----------|
| **dbt-loom** | ✅ Yes | ❌ No | Medium | Isolated deployments |
| **Native Sources** | ⚠️ Compile only | ✅ Yes | Low | Shared database setups |
| **State Deferral** | ❌ No | ✅ Yes | Low | Monorepo same-project |

## 1. dbt-loom Plugin Approach ✅ Recommended for CI/CD

### How It Works
- Downloads upstream manifest from S3
- Injects upstream models into dbt's parse tree at runtime
- References via `{{ ref('upstream_project', 'model_name') }}`

### CI/CD Workflow
```yaml
- Sync manifest from S3
- dbt build  # Works! dbt-loom resolves refs
- Validate lineage
```

### Advantages
✅ Works with isolated databases (each project has own DB)
✅ Full build capability in CI/CD
✅ True cross-project lineage in manifest
✅ No database configuration needed

### Disadvantages
❌ Requires plugin installation
❌ Plugin overhead in parse phase
❌ Not "native" dbt

### When to Use
- **Isolated deployments**: Each project deploys to separate environments
- **Different databases**: Projects use different database instances
- **Microservices pattern**: Projects owned by different teams
- **CI/CD pipelines**: GitHub Actions, GitLab CI, etc.

### Example Workflow
```bash
# Upstream
cd dbt_up
dbt build
python3 publish_manifest.py --bucket my-bucket

# Downstream (in separate CI/CD job)
cd dbt_down_loom
# dbt-loom automatically fetches manifest from S3
dbt build  # ✅ Works!
```

---

## 2. Native Sources Approach ⚠️ Limited CI/CD Support

### How It Works
- Downloads upstream manifest from S3
- Generates `sources.yml` with upstream models as sources
- References via `{{ source('upstream_project', 'model_name') }}`

### CI/CD Workflow
```yaml
- Sync manifest from S3 + generate sources
- dbt compile  # ⚠️ Compile only
- Validate lineage
- dbt build    # ❌ Fails without shared database
```

### Advantages
✅ Native dbt (no plugins)
✅ Simple conceptually
✅ Lineage tracking works
✅ Good for local development

### Disadvantages
❌ **Cannot build in isolated CI/CD** - source table doesn't exist
❌ Requires shared database for full builds
❌ Source definitions need database configuration
❌ Compile-only validation in CI/CD

### When to Use
- **Shared database**: All projects deploy to same database
- **Monorepo**: All projects in one repository
- **Local development**: Testing cross-project refs locally
- **PostgreSQL/Snowflake**: When using shared data warehouse

### Example Workflow
```bash
# Upstream (deploys to shared DB)
cd dbt_up
dbt build --target prod  # Builds to production.schema_a

# Downstream (same DB)
cd dbt_down
python3 scripts/sync_mesh.py --bucket my-bucket
# Generated source points to production.schema_a.public_orders
dbt build --target prod  # ✅ Works! Table exists in same DB
```

### CI/CD Limitation
```bash
# In GitHub Actions with isolated databases:
cd dbt_down
python3 scripts/sync_mesh.py
dbt compile  # ✅ Works - validates SQL
dbt build    # ❌ Fails - table doesn't exist in this DuckDB instance
```

---

## 3. State Deferral ❌ Not for Cross-Project

### How It Works
- Uses `--state` and `--defer` flags
- Defers to upstream state for **same project** development
- Mainly for CI optimization, not cross-project refs

### Why It Doesn't Work for Mesh
```bash
# This is what --defer is designed for:
git checkout feature-branch
dbt build --select state:modified --defer --state prod/

# NOT for cross-project:
cd downstream_project
dbt build --defer --state ../upstream_project/  # ❌ Wrong use case
```

The `--defer` flag is for deferring **to production state of same project**, not for cross-project dependencies.

---

## Recommendations by Setup

### GitHub Actions / GitLab CI (Isolated Databases)
```
✅ Use dbt-loom plugin
❌ Don't use native sources (compile-only)
```

**Why**: Each CI job has isolated database. Upstream tables don't exist in downstream jobs.

### Shared Data Warehouse (PostgreSQL, Snowflake, BigQuery)
```
✅ Use native sources (simple, no plugins)
✅ Use dbt-loom (also works, more flexibility)
```

**Why**: All projects deploy to same database. Upstream tables exist and accessible.

### Monorepo (All Projects Together)
```
✅ Use native sources (simplest)
✅ Use dbt-loom (if need stronger separation)
```

**Why**: Can build all projects sequentially with shared database context.

### Microservices / Multi-Repo
```
✅ Use dbt-loom plugin (only option)
```

**Why**: Projects are truly independent with separate databases and deployments.

---

## This POC Setup

Our GitHub Actions workflows demonstrate both approaches:

### `upstream/dbt_up` Branch
```yaml
✅ Builds models
✅ Publishes manifest to S3
✅ Works in CI/CD
```

### `downstream/dbt_down_loom` Branch
```yaml
✅ Downloads manifest via dbt-loom
✅ Builds models successfully
✅ Works in CI/CD - Full build capability
```

### `downstream/dbt_down` Branch
```yaml
⚠️ Downloads manifest + generates sources
⚠️ Compiles models successfully
⚠️ Validates lineage tracking
❌ Cannot build - no shared database
```

---

## Migration Path

### Starting with Native Sources
If you start with native sources approach:

```bash
# 1. Works initially with shared DB
cd dbt_down
python3 scripts/sync_mesh.py
dbt build  # ✅ Works

# 2. CI/CD fails with isolated DBs
# GitHub Actions: ❌ Table doesn't exist

# 3. Migrate to dbt-loom
pip install dbt-loom
# Create dbt_loom.config.yml
dbt build  # ✅ Works in CI/CD now
```

### Starting with dbt-loom
If you start with dbt-loom:

```bash
# Works everywhere from day 1
dbt build  # ✅ Works in CI/CD
dbt build  # ✅ Works locally
dbt build  # ✅ Works with shared or isolated DB
```

---

## Cost Comparison

### dbt Cloud Enterprise ($3,000/month)
- Full mesh support built-in
- Discovery API
- Cross-project lineage UI
- Automatic manifest management

### dbt-loom Plugin (Free + S3 costs)
- Same core functionality
- S3 manifest storage (~$1/month)
- Manual CI/CD setup
- No GUI (use dbt docs)

**Savings: $2,999/month** 💰

---

## Conclusion

For **production CI/CD with isolated deployments**:
- ✅ **Use dbt-loom plugin**
- ⚠️ Native sources = compile-only validation
- ❌ State deferral = wrong use case

For **shared database setups**:
- ✅ Native sources (simpler)
- ✅ dbt-loom (more flexible)

The dbt-loom plugin approach is the most versatile and recommended for modern CI/CD pipelines.
