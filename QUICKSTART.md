# Quick Start Guide

## 🚀 In 5 Minutes

### 1. Push Current Changes
```bash
git push origin main
```

### 2. Set GitHub Secrets

Go to: https://github.com/luongnamkhanh/dbt_mesh/settings/secrets/actions

Click **"New repository secret"** three times to add:

```
Name: AWS_ACCESS_KEY_ID
Value: ASIA5REPIDEWLHMXY7GL

Name: AWS_SECRET_ACCESS_KEY
Value: wQMWxk+1+e0Yo7D/T9TVksfPztHqOBAvttzEfDyN

Name: AWS_SESSION_TOKEN
Value: IQoJb3JpZ2luX2VjECgaDmFwLXNv... (paste full token)
```

### 3. Create S3 Bucket

```bash
# Create bucket (choose unique name)
aws s3 mb s3://dbt-mesh-registry-YOUR_NAME --region ap-southeast-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket dbt-mesh-registry-YOUR_NAME \
  --versioning-configuration Status=Enabled \
  --region ap-southeast-1
```

### 4. Update Workflow Files

```bash
# Replace bucket name in all workflows
sed -i 's/your-dbt-mesh-bucket/dbt-mesh-registry-YOUR_NAME/g' .github/workflows/*.yml

# Commit
git add .github/workflows/
git commit -m "Configure S3 bucket name"
git push origin main
```

### 5. Create Branches

```bash
# Upstream branch
git checkout -b upstream/dbt_up
git filter-repo --subdirectory-filter dbt_up --force
# Or manually: git rm -rf dbt_down dbt_down_loom plan.md etc.
git push -u origin upstream/dbt_up

# Repeat for downstream branches (see BRANCHING.md)
```

### 6. Watch It Run! 🎉

Go to: https://github.com/luongnamkhanh/dbt_mesh/actions

You should see workflows running automatically!

## 📚 Full Documentation

- [SETUP.md](SETUP.md) - Complete setup guide
- [BRANCHING.md](BRANCHING.md) - Branch restructuring details
- [README.md](README.md) - Project overview
- [CLAUDE.md](CLAUDE.md) - Developer guide

## ⚠️ Important Notes

**Session Token Expiry:**
Your AWS credentials are temporary. When they expire:
1. Get new credentials from AWS
2. Update GitHub Secrets with new values
3. No code changes needed!

**Don't Commit Credentials:**
All AWS credentials should ONLY be in GitHub Secrets, never in code.
