#!/usr/bin/env python3
"""
Manifest Publisher for dbt Mesh Registry

Publishes dbt manifest.json to S3 registry with:
- latest/ partition: Current contract (overwritten)
- history/ partition: Timestamped audit trail

Usage:
    python publish_manifest.py [--local] [--bucket BUCKET] [--env ENV]

For local testing (no S3):
    python publish_manifest.py --local
"""

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

# Optional boto3 import for S3 mode
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def get_manifest_path() -> Path:
    """Get path to compiled manifest.json"""
    manifest_path = Path(__file__).parent / "target" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found at {manifest_path}. "
            "Run 'dbt compile' or 'dbt build' first."
        )
    return manifest_path


def publish_local(manifest_path: Path, project_name: str, env: str, registry_base: Path):
    """Publish manifest to local filesystem (S3 simulation)"""
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Define paths
    latest_dir = registry_base / project_name / env / "latest"
    history_dir = registry_base / project_name / env / "history" / timestamp

    # Create directories
    latest_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    # Copy manifest to both locations
    latest_path = latest_dir / "manifest.json"
    history_path = history_dir / "manifest.json"

    shutil.copy2(manifest_path, latest_path)
    shutil.copy2(manifest_path, history_path)

    print(f"✓ Published to local registry:")
    print(f"  Latest:  {latest_path}")
    print(f"  History: {history_path}")

    return str(latest_path), str(history_path)


def publish_s3(manifest_path: Path, project_name: str, env: str, bucket: str):
    """Publish manifest to S3 registry"""
    if not HAS_BOTO3:
        raise ImportError("boto3 required for S3 publishing. Install with: pip install boto3")

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    s3_client = boto3.client('s3')

    # Define S3 keys
    latest_key = f"registry/{project_name}/{env}/latest/manifest.json"
    history_key = f"registry/{project_name}/{env}/history/{timestamp}/manifest.json"

    # Read manifest content
    with open(manifest_path, 'r') as f:
        manifest_content = f.read()

    # Upload to both locations
    s3_client.put_object(
        Bucket=bucket,
        Key=latest_key,
        Body=manifest_content,
        ContentType='application/json'
    )

    s3_client.put_object(
        Bucket=bucket,
        Key=history_key,
        Body=manifest_content,
        ContentType='application/json'
    )

    print(f"✓ Published to S3 registry:")
    print(f"  Latest:  s3://{bucket}/{latest_key}")
    print(f"  History: s3://{bucket}/{history_key}")

    return f"s3://{bucket}/{latest_key}", f"s3://{bucket}/{history_key}"


def main():
    parser = argparse.ArgumentParser(description="Publish dbt manifest to mesh registry")
    parser.add_argument("--local", action="store_true", help="Use local filesystem instead of S3")
    parser.add_argument("--bucket", default=os.environ.get("DBT_MESH_BUCKET"), help="S3 bucket name")
    parser.add_argument("--env", default="prod", help="Environment (dev/staging/prod)")
    parser.add_argument("--project", default="dbt_up", help="Project name for registry path")
    parser.add_argument("--registry-path", default="../registry", help="Local registry base path")

    args = parser.parse_args()

    # Get manifest path
    manifest_path = get_manifest_path()
    print(f"Found manifest: {manifest_path}")

    # Validate manifest has public models
    with open(manifest_path) as f:
        manifest = json.load(f)

    public_models = [
        node_id for node_id, node in manifest.get("nodes", {}).items()
        if node.get("resource_type") == "model" and node.get("access") == "public"
    ]

    if not public_models:
        print("⚠ Warning: No public models found in manifest")
    else:
        print(f"Found {len(public_models)} public model(s): {public_models}")

    # Publish
    if args.local:
        registry_base = Path(__file__).parent / args.registry_path
        publish_local(manifest_path, args.project, args.env, registry_base)
    else:
        if not args.bucket:
            raise ValueError("S3 bucket required. Set --bucket or DBT_MESH_BUCKET env var")
        publish_s3(manifest_path, args.project, args.env, args.bucket)

    print("\n✓ Manifest published successfully!")


if __name__ == "__main__":
    main()
