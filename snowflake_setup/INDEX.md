# Snowflake dbt Mesh Setup - Complete Guide

Welcome! This directory contains everything you need to set up a production-ready dbt mesh architecture on Snowflake.

## 📋 What You'll Build

A multi-project dbt mesh setup with:
- **1 Upstream project** (dbt_up) - Publishes core data models
- **2 Downstream projects** (dbt_down, dbt_down_loom) - Consume upstream models
- **Persistent Snowflake warehouse** - Enables true `--defer` functionality
- **CI/CD ready** - GitHub Actions workflows included

## 🚀 Quick Start (30 minutes)

### Step 1: Run Snowflake Setup Scripts (10 min)

Run these SQL scripts in order using Snowsight UI or SnowSQL:

```bash
# Connect to Snowflake
snowsql -a QMVBJWG-PM06063 -u KHANHLN

# Run setup scripts
!source 01_create_databases_and_warehouses.sql
!source 02_create_roles_and_users.sql
!source 03_create_sample_data.sql
!source 04_verify_setup.sql  # Verify everything works
```

**See**: `README.md` for detailed instructions

### Step 2: Configure dbt (5 min)

```bash
# Set password
export DBT_SNOWFLAKE_PASSWORD='your_password'

# Copy profiles
cp snowflake_setup/profiles.yml ~/.dbt/profiles.yml

# Test connection
cd dbt_up && dbt debug
```

**See**: `QUICKSTART.md` for detailed walkthrough

### Step 3: Run Your First Mesh Build (5 min)

```bash
# Build upstream
cd dbt_up
dbt build

# Build downstream (reads from upstream!)
cd ../dbt_down
dbt build --defer --state ../dbt_up/target
```

**See**: `QUICKSTART.md` section "Step 5-7"

### Step 4: Deploy to CI/CD (10 min)

Update GitHub Actions workflows to use Snowflake credentials.

**See**: `QUICKSTART.md` section "Step 9"

## 📁 Files in This Directory

### Setup Scripts (Run in Order)
1. **`01_create_databases_and_warehouses.sql`**
   - Creates 3 databases, 2 warehouses, 7 schemas
   - Run time: ~30 seconds

2. **`02_create_roles_and_users.sql`**
   - Creates 3 functional roles with proper permissions
   - Grants cross-database read access for mesh
   - Run time: ~10 seconds

3. **`03_create_sample_data.sql`**
   - Creates raw source tables (orders, customers)
   - Loads 10 sample orders, 6 customers
   - Run time: ~5 seconds

4. **`04_verify_setup.sql`**
   - Verification checks for all components
   - Run this to ensure everything worked
   - Run time: ~10 seconds

### Configuration Files
- **`profiles.yml`** - dbt connection profiles for all 3 projects
- **`setup_keypair_auth.sh`** - Script to generate SSH keys (more secure than passwords)

### Documentation
- **`README.md`** - Setup instructions and troubleshooting
- **`QUICKSTART.md`** - Step-by-step walkthrough with code examples
- **`ARCHITECTURE.md`** - Deep dive into mesh architecture, data flow, and best practices
- **`INDEX.md`** (this file) - Overview and navigation

## 🎯 What Gets Created

### Warehouses (Compute)
```
DBT_UP_WH       - For upstream builds (XSMALL, auto-suspend 60s)
DBT_DOWN_WH     - For downstream builds (XSMALL, auto-suspend 60s)
```

### Databases & Schemas
```
DBT_UP_PROD
├── RAW             ← Source data (orders, customers)
├── STAGING         ← Staging models
└── MARTS           ← Public models for mesh

DBT_DOWN_PROD
├── STAGING         ← Downstream staging
└── MARTS           ← Downstream marts

DBT_DOWN_LOOM_PROD
├── STAGING         ← Downstream staging (dbt-loom)
└── MARTS           ← Downstream marts (dbt-loom)
```

### Roles & Permissions
```
DBT_UP_ROLE
├── Full access to DBT_UP_PROD
└── Builds upstream models

DBT_DOWN_ROLE
├── Full access to DBT_DOWN_PROD
├── READ access to DBT_UP_PROD (for mesh)
└── Builds downstream models

DBT_DOWN_LOOM_ROLE
├── Full access to DBT_DOWN_LOOM_PROD
├── READ access to DBT_UP_PROD (for mesh)
└── Builds downstream models (dbt-loom approach)
```

## 📖 Read These Docs

### For Setup & Configuration
- Start here: **`README.md`**
- Hands-on guide: **`QUICKSTART.md`**

### For Understanding Architecture
- Architecture deep dive: **`ARCHITECTURE.md`**
- Covers: data flow, lineage, access control, deployment patterns

### For Security
- Key-pair auth setup: Run `./setup_keypair_auth.sh`
- Best practices in: **`ARCHITECTURE.md`** > Security section

## 🎓 Key Concepts

### What is dbt Mesh?
Cross-project model dependencies where:
- **Upstream** publishes models with `access: public`
- **Downstream** references them via `source()` or dbt-loom
- Projects deploy independently but share data

### Why Snowflake?
- **Persistent warehouse** - Tables survive between CI runs
- **--defer works** - Downstream can skip rebuilding upstream
- **Production ready** - Used by thousands of companies
- **Cost effective** - Auto-suspend keeps costs low

### Two Mesh Approaches

#### 1. Native dbt (dbt_down)
```yaml
# Generate source from manifest
source('dbt_up', 'public_orders')
```
**Pros**: Official dbt feature, explicit sources
**Cons**: Requires manifest sync script

#### 2. dbt-loom (dbt_down_loom)
```yaml
# Automatic resolution via package
ref('dbt_up', 'public_orders')
```
**Pros**: Automatic, less boilerplate
**Cons**: Third-party package, newer

## 🔍 Troubleshooting

### Setup fails?
1. Check you're running as `ACCOUNTADMIN` role
2. Verify account ID: `QMVBJWG-PM06063`
3. Run `04_verify_setup.sql` to diagnose

### dbt can't connect?
```bash
# Check password is set
echo $DBT_SNOWFLAKE_PASSWORD

# Test connection
dbt debug --profiles-dir ~/.dbt
```

### Downstream can't read upstream?
```sql
-- Check permissions
USE ROLE ACCOUNTADMIN;
SHOW GRANTS TO ROLE DBT_DOWN_ROLE;
```

### More help?
See **`README.md`** > Troubleshooting section

## 💰 Cost Estimate

**Expected monthly cost for demo usage:**
- XSMALL warehouses: $2/hour (only when running)
- Auto-suspend after 60 seconds
- Typical usage: < 5 hours/month
- **Total: < $10/month**

**Tips to minimize cost:**
- Suspend warehouses when not in use
- Use development databases for testing
- Delete databases when done: See `QUICKSTART.md` cleanup section

## ✅ Verification Checklist

After setup, verify:
- [ ] 2 warehouses created (DBT_UP_WH, DBT_DOWN_WH)
- [ ] 3 databases created (DBT_UP_PROD, DBT_DOWN_PROD, DBT_DOWN_LOOM_PROD)
- [ ] 3 roles created (DBT_UP_ROLE, DBT_DOWN_ROLE, DBT_DOWN_LOOM_ROLE)
- [ ] Sample data loaded (10 orders, 6 customers)
- [ ] `dbt debug` passes for all projects
- [ ] Upstream builds successfully: `cd dbt_up && dbt build`
- [ ] Downstream reads upstream: `cd dbt_down && dbt build --defer`

Run `04_verify_setup.sql` to check all items automatically!

## 🆘 Support

- **Setup issues?** → See `README.md`
- **Architecture questions?** → See `ARCHITECTURE.md`
- **Step-by-step help?** → See `QUICKSTART.md`
- **dbt mesh docs:** https://docs.getdbt.com/docs/collaborate/govern/project-dependencies
- **Snowflake docs:** https://docs.snowflake.com/en/user-guide/ecosystem-dbt

## 🎉 Next Steps After Setup

1. **Test locally** - Build all projects
2. **Explore lineage** - Run `dbt docs generate && dbt docs serve`
3. **Update CI/CD** - Configure GitHub Actions with Snowflake
4. **Add models** - Extend with your own transformations
5. **Go to production** - Deploy for real workloads

## 📝 Quick Reference

```bash
# Setup (one time)
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 01_create_databases_and_warehouses.sql
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 02_create_roles_and_users.sql
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 03_create_sample_data.sql

# Build upstream
cd dbt_up && dbt build

# Build downstream (with defer)
cd dbt_down && dbt build --defer --state ../dbt_up/target

# View docs
dbt docs generate && dbt docs serve

# Verify setup
snowsql -a QMVBJWG-PM06063 -u KHANHLN -f 04_verify_setup.sql
```

---

**Ready to get started?** → Open **`QUICKSTART.md`** and follow along! 🚀
