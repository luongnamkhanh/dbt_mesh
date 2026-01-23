# Branch Restructuring Guide

This guide explains how to convert the monorepo into separate branches for production-like workflows.

## Why Separate Branches?

- **Team autonomy**: Each project owned by different teams
- **Independent CI/CD**: Build and deploy cycles per project
- **Access control**: Branch protection rules per team
- **Realistic simulation**: Mirrors production mesh architecture

## Branch Structure

```
main                          # Documentation + shared utilities
├── upstream/dbt_up          # Upstream project team
├── downstream/dbt_down_loom # Consumer team A (loom approach)
└── downstream/dbt_down      # Consumer team B (native approach)
```

## Step 1: Prepare Main Branch

The main branch should contain:
- Documentation (README.md, CLAUDE.md, plan.md)
- Shared utilities (validate_lineage.py, requirements.txt)
- GitHub workflows
- Branch setup scripts

```bash
# Ensure you're on main with latest changes
git checkout main
git pull origin main

# Verify GitHub workflows exist
ls -la .github/workflows/
```

## Step 2: Create Upstream Branch

```bash
# Create and switch to upstream branch
git checkout -b upstream/dbt_up

# Keep only upstream project files
git rm -rf dbt_down dbt_down_loom
git rm -f plan.md BRANCHING.md

# Keep essential files for the project
# Structure should be:
# - dbt_up/
# - requirements.txt
# - .github/workflows/upstream.yml
# - .gitignore

# Commit the cleaned branch
git add -A
git commit -m "Initialize upstream branch with dbt_up project

- Contains public models with access controls
- CI/CD workflow for manifest publishing
- S3 registry integration

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Push to remote
git push -u origin upstream/dbt_up
```

## Step 3: Create Downstream Loom Branch

```bash
# Go back to main
git checkout main

# Create downstream loom branch
git checkout -b downstream/dbt_down_loom

# Keep only loom project files
git rm -rf dbt_up dbt_down
git rm -f plan.md BRANCHING.md

# Keep:
# - dbt_down_loom/
# - requirements.txt
# - validate_lineage.py (for CI validation)
# - .github/workflows/downstream-loom.yml
# - .gitignore

git add -A
git commit -m "Initialize downstream loom branch

- Uses dbt-loom plugin for cross-project refs
- CI/CD workflow with S3 manifest sync
- Lineage validation in pipeline

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push -u origin downstream/dbt_down_loom
```

## Step 4: Create Downstream Native Branch

```bash
# Go back to main
git checkout main

# Create downstream native branch
git checkout -b downstream/dbt_down

# Keep only native project files
git rm -rf dbt_up dbt_down_loom
git rm -f plan.md BRANCHING.md

# Keep:
# - dbt_down/
# - requirements.txt
# - validate_lineage.py (for CI validation)
# - .github/workflows/downstream-native.yml
# - .gitignore

git add -A
git commit -m "Initialize downstream native branch

- Uses auto-generated sources from upstream manifest
- Native dbt approach without plugins
- CI/CD workflow with manifest sync and source generation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push -u origin downstream/dbt_down
```

## Step 5: Clean Up Main Branch

```bash
# Return to main
git checkout main

# Remove project directories (keep docs and utilities)
git rm -rf dbt_up dbt_down dbt_down_loom registry
git rm -f profiles.yml.example

# Main should contain:
# - README.md
# - CLAUDE.md
# - BRANCHING.md
# - plan.md
# - validate_lineage.py
# - requirements.txt
# - .github/workflows/ (all workflows)
# - .gitignore

git add -A
git commit -m "Clean main branch - documentation only

Main branch now serves as documentation and CI/CD hub.
Active development happens on project-specific branches.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push origin main
```

## Step 6: Configure GitHub Settings

### Branch Protection Rules

For each branch, go to Settings → Branches → Add rule:

**upstream/dbt_up:**
- ✓ Require pull request reviews before merging
- ✓ Require status checks to pass: `build-and-publish`
- ✓ Require branches to be up to date

**downstream/* branches:**
- ✓ Require pull request reviews before merging
- ✓ Require status checks to pass: `build`
- ✓ Require branches to be up to date

### GitHub Secrets

Add AWS credentials (Settings → Secrets and variables → Actions):

```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN (if using temporary credentials)
```

### Environment Variables

Update `DBT_MESH_BUCKET` in each workflow file with your S3 bucket name.

## Step 7: Test Workflows

```bash
# Trigger upstream build
git checkout upstream/dbt_up
git commit --allow-empty -m "Test CI/CD workflow"
git push

# Check GitHub Actions tab for workflow run

# Trigger downstream builds
git checkout downstream/dbt_down_loom
git commit --allow-empty -m "Test CI/CD workflow"
git push

git checkout downstream/dbt_down
git commit --allow-empty -m "Test CI/CD workflow"
git push
```

## Development Workflow

### Making Changes to Upstream

```bash
git checkout upstream/dbt_up
git pull origin upstream/dbt_up

# Make changes to models
vim dbt_up/models/public_orders.sql

# Commit and push
git add .
git commit -m "Update public_orders model"
git push

# CI will build and publish manifest to S3
```

### Making Changes to Downstream

```bash
git checkout downstream/dbt_down_loom
git pull origin downstream/dbt_down_loom

# Make changes
vim dbt_down_loom/models/downstream_orders.sql

# Commit and push
git add .
git commit -m "Add new transformation logic"
git push

# CI will sync latest upstream manifest and build
```

## Rollback Strategy

Each branch maintains its own history. To rollback:

```bash
# Rollback upstream
git checkout upstream/dbt_up
git revert <commit-hash>
git push

# Downstream projects automatically use latest manifest
```

## Tips

1. **Keep main updated**: Merge workflow changes from main to project branches periodically
2. **Manifest versions**: Use S3 versioning for manifest rollback capability
3. **Testing**: Use `workflow_dispatch` trigger to manually test CI/CD
4. **Local development**: Clone all branches to test locally:
   ```bash
   git clone -b upstream/dbt_up <repo-url> upstream
   git clone -b downstream/dbt_down_loom <repo-url> downstream_loom
   git clone -b downstream/dbt_down <repo-url> downstream_native
   ```

## Troubleshooting

**Workflow fails with AWS auth error:**
- Check GitHub Secrets are set correctly
- Verify AWS credentials haven't expired (especially session tokens)

**Lineage validation fails:**
- Check upstream manifest was published successfully
- Verify S3 bucket name is correct in workflow env vars
- Check dbt-loom config references correct S3 path

**Cannot find upstream manifest:**
- Ensure upstream CI completed successfully first
- Check S3 bucket permissions
- Verify bucket name and path in downstream scripts
