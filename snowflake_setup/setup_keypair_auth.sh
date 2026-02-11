#!/bin/bash
# ============================================================================
# Setup Key-Pair Authentication for Snowflake (More Secure than Password)
# ============================================================================
# This script generates RSA key pairs for secure Snowflake authentication
# Run this locally, then upload public key to Snowflake
# ============================================================================

set -e

echo "=== Snowflake Key-Pair Authentication Setup ==="
echo ""

# Configuration
KEY_DIR="$HOME/.ssh/snowflake"
KEY_NAME="snowflake_rsa_key"
PRIVATE_KEY="$KEY_DIR/${KEY_NAME}.p8"
PUBLIC_KEY="$KEY_DIR/${KEY_NAME}.pub"

# Create directory
echo "1. Creating key directory: $KEY_DIR"
mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

# Generate private key
echo "2. Generating RSA private key..."
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out "$PRIVATE_KEY" -nocrypt

# Generate public key
echo "3. Generating public key..."
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"

# Set permissions
chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo ""
echo "✓ Keys generated successfully!"
echo ""
echo "Private key: $PRIVATE_KEY"
echo "Public key: $PUBLIC_KEY"
echo ""

# Extract public key value for Snowflake
echo "=== Next Steps ==="
echo ""
echo "1. Copy the public key value (without header/footer):"
echo ""
grep -v "BEGIN PUBLIC KEY" "$PUBLIC_KEY" | grep -v "END PUBLIC KEY" | tr -d '\n'
echo ""
echo ""
echo "2. Run this SQL in Snowflake as ACCOUNTADMIN:"
echo ""
cat << 'EOF'
USE ROLE ACCOUNTADMIN;

-- For your user account
ALTER USER KHANHLN SET RSA_PUBLIC_KEY='<paste_public_key_here>';

-- Or for a CI service account (if created)
-- ALTER USER DBT_CI_USER SET RSA_PUBLIC_KEY='<paste_public_key_here>';

-- Verify
DESC USER KHANHLN;
EOF
echo ""
echo "3. Update your ~/.dbt/profiles.yml to use key authentication:"
echo ""
cat << 'EOF'
dbt_up:
  target: prod
  outputs:
    prod:
      type: snowflake
      account: QMVBJWG-PM06063
      user: KHANHLN
      authenticator: snowflake_jwt
      private_key_path: ~/.ssh/snowflake/snowflake_rsa_key.p8
      role: DBT_UP_ROLE
      warehouse: DBT_UP_WH
      database: DBT_UP_PROD
      schema: STAGING
      threads: 4
EOF
echo ""
echo "4. Test connection:"
echo "   cd dbt_up && dbt debug"
echo ""
echo "=== For GitHub Actions CI/CD ==="
echo ""
echo "1. Copy private key content:"
echo "   cat $PRIVATE_KEY"
echo ""
echo "2. Add as GitHub Secret: SNOWFLAKE_PRIVATE_KEY"
echo "   - Go to repo Settings > Secrets and variables > Actions"
echo "   - Add new secret with the entire key content (including BEGIN/END lines)"
echo ""
echo "3. Update workflow to use key auth:"
echo ""
cat << 'EOF'
- name: Configure dbt profiles
  run: |
    mkdir -p ~/.dbt ~/.ssh

    # Write private key from secret
    echo "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > ~/.ssh/snowflake_key.p8
    chmod 600 ~/.ssh/snowflake_key.p8

    # Create profiles.yml with key auth
    cat > ~/.dbt/profiles.yml <<PROFILE
    dbt_down:
      target: prod
      outputs:
        prod:
          type: snowflake
          account: QMVBJWG-PM06063
          user: KHANHLN
          authenticator: snowflake_jwt
          private_key_path: ~/.ssh/snowflake_key.p8
          role: DBT_DOWN_ROLE
          warehouse: DBT_DOWN_WH
          database: DBT_DOWN_PROD
          schema: STAGING
          threads: 4
    PROFILE
EOF
echo ""
echo "✓ Setup complete!"
