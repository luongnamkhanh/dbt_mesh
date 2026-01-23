# Setup Guide

## Prerequisites

1. AWS account with S3 access
2. GitHub repository
3. Python 3.9+

## 1. Configure GitHub Secrets

### Navigate to Secrets Settings

Go to: `https://github.com/YOUR_USERNAME/dbt_mesh/settings/secrets/actions`

### Add AWS Credentials

Click **"New repository secret"** and add:

| Secret Name | Value | Notes |
|-------------|-------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | Never commit to code |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | Never commit to code |
| `AWS_SESSION_TOKEN` | Your session token | Only if using temporary credentials |

**How to get values:**
```bash
# From your terminal (these should never go in git)
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $AWS_SESSION_TOKEN
```

### Verify Secrets Are Set

After adding, you should see:
- ✓ AWS_ACCESS_KEY_ID
- ✓ AWS_SECRET_ACCESS_KEY
- ✓ AWS_SESSION_TOKEN

## 2. Create S3 Bucket

```bash
# Set your bucket name (must be globally unique)
export BUCKET_NAME="dbt-mesh-registry-$(date +%s)"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ap-southeast-1

# Enable versioning (for manifest history)
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled \
  --region ap-southeast-1

# Verify
aws s3 ls
echo "✓ Bucket created: ${BUCKET_NAME}"
```

## 3. Update Workflow Files

Edit the `DBT_MESH_BUCKET` variable in each workflow:

### .github/workflows/upstream.yml
```yaml
env:
  DBT_MESH_BUCKET: YOUR_BUCKET_NAME_HERE  # Replace this
  AWS_REGION: ap-southeast-1
```

### .github/workflows/downstream-loom.yml
```yaml
env:
  DBT_MESH_BUCKET: YOUR_BUCKET_NAME_HERE  # Replace this
  AWS_REGION: ap-southeast-1
```

### .github/workflows/downstream-native.yml
```yaml
env:
  DBT_MESH_BUCKET: YOUR_BUCKET_NAME_HERE  # Replace this
  AWS_REGION: ap-southeast-1
```

**Quick replace:**
```bash
# Replace in all workflow files
BUCKET_NAME="your-actual-bucket-name"
find .github/workflows -name "*.yml" -type f -exec sed -i \
  "s/your-dbt-mesh-bucket/${BUCKET_NAME}/g" {} \;

# Verify
grep DBT_MESH_BUCKET .github/workflows/*.yml
```

## 4. Commit and Push

```bash
# Add changes
git add .github/workflows/

# Commit
git commit -m "Configure S3 bucket for mesh registry"

# Push to trigger first workflow
git push origin main
```

## 5. Restructure Into Branches

Follow the detailed guide in [BRANCHING.md](BRANCHING.md):

```bash
# Quick version:
# 1. Create upstream branch
git checkout -b upstream/dbt_up
git rm -rf dbt_down dbt_down_loom plan.md BRANCHING.md SETUP.md
git commit -m "Initialize upstream branch"
git push -u origin upstream/dbt_up

# 2. Create downstream branches (repeat for each)
git checkout main
git checkout -b downstream/dbt_down_loom
# ... (see BRANCHING.md for full steps)
```

## 6. Test CI/CD Pipeline

### Test Upstream Build

```bash
git checkout upstream/dbt_up
git commit --allow-empty -m "Test upstream CI/CD"
git push
```

Go to: `https://github.com/YOUR_USERNAME/dbt_mesh/actions`

You should see:
- ✓ Upstream - Build and Publish (running/completed)

### Test Downstream Build

```bash
# Wait for upstream to complete first!

git checkout downstream/dbt_down_loom
git commit --allow-empty -m "Test downstream CI/CD"
git push
```

Check Actions tab again:
- ✓ Downstream Loom - Build and Test (running/completed)

## 7. Verify S3 Registry

```bash
# Check manifest was published
aws s3 ls s3://${BUCKET_NAME}/registry/dbt_up/prod/latest/

# Expected output:
# 2026-01-23 06:45:41    123456 manifest.json

# Check history
aws s3 ls s3://${BUCKET_NAME}/registry/dbt_up/prod/history/

# Expected: timestamped directories
```

## Troubleshooting

### Workflow fails with "Could not resolve host: github.com"
- Network/firewall issue in GitHub Actions
- Try re-running the workflow

### AWS authentication error
```
Error: The security token included in the request is invalid
```

**Solution**: Your AWS credentials expired. Update GitHub Secrets with new credentials:
```bash
# Get new credentials
aws sts get-session-token --duration-seconds 43200

# Update GitHub Secrets with new values
```

### Manifest not found in S3
```
Error: An error occurred (404) when calling the HeadObject operation
```

**Solution**: Upstream build must complete first
1. Check upstream workflow completed successfully
2. Verify bucket name is correct in workflow files
3. Check S3 permissions

### Lineage validation fails
```
✗ FAIL: No cross-project references found
```

**Solution**: Check dbt-loom config or sources generation
```bash
# For dbt_down_loom: verify dbt_loom.config.yml
cat dbt_down_loom/dbt_loom.config.yml

# For dbt_down: check generated sources file
cat dbt_down/models/_mesh_dbt_up.yml
```

## Security Best Practices

### ✅ DO:
- Store credentials in GitHub Secrets
- Use temporary credentials with session tokens
- Enable S3 bucket versioning
- Rotate credentials regularly
- Use IAM roles in production

### ❌ DON'T:
- Commit credentials to git
- Share credentials in issues/PRs
- Use root AWS credentials
- Disable branch protection rules
- Skip lineage validation

## AWS IAM Policy

For production, create an IAM user with this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DBTMeshRegistry",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME/*",
        "arn:aws:s3:::YOUR_BUCKET_NAME"
      ]
    }
  ]
}
```

## Next Steps

1. ✓ Configure GitHub Secrets
2. ✓ Create S3 bucket
3. ✓ Update workflow files
4. ✓ Push to main
5. ✓ Restructure into branches
6. ✓ Test CI/CD pipelines
7. → Add branch protection rules
8. → Set up notifications
9. → Document team workflows

## Support

See [README.md](README.md) for project overview and [BRANCHING.md](BRANCHING.md) for detailed branch setup.
