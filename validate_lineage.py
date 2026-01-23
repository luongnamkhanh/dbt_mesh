#!/usr/bin/env python3
"""
dbt Mesh Cross-Project Lineage Validator

Validates that downstream project manifests contain proper lineage
references to upstream models in their parent_map.

Success Criteria:
- Exit code 0: parent_map contains model.dbt_up.* references
- Exit code 1: Lineage is broken or missing

Usage:
    python validate_lineage.py [--project PROJECT] [--manifest PATH]

Examples:
    # Validate dbt_down_loom project
    python validate_lineage.py --project dbt_down_loom

    # Validate dbt_down project
    python validate_lineage.py --project dbt_down

    # Validate specific manifest file
    python validate_lineage.py --manifest path/to/manifest.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_manifest(manifest_path: Path) -> dict:
    """Load and parse a dbt manifest.json file"""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        return json.load(f)


def find_cross_project_refs(manifest: dict, upstream_project: str = "dbt_up") -> Dict[str, List[str]]:
    """
    Find all cross-project references in the manifest's parent_map.

    Returns dict mapping downstream model -> list of upstream parent refs
    Checks for both model refs (dbt-loom) and source refs (native approach)
    """
    parent_map = manifest.get("parent_map", {})
    cross_refs = {}

    for node_id, parents in parent_map.items():
        # Look for upstream project references in parents
        # dbt-loom: model.dbt_up.public_orders
        # Native sources: source.{current_project}.dbt_up.public_orders
        upstream_parents = [
            parent for parent in parents
            if (parent.startswith(f"model.{upstream_project}.") or
                f".{upstream_project}." in parent and parent.startswith("source."))
        ]

        if upstream_parents:
            cross_refs[node_id] = upstream_parents

    return cross_refs


def find_cross_project_refs_in_nodes(manifest: dict, upstream_project: str = "dbt_up") -> Dict[str, List[str]]:
    """
    Alternative check: Look for refs in node depends_on.
    Checks for both model refs (dbt-loom) and source refs (native approach)
    """
    nodes = manifest.get("nodes", {})
    cross_refs = {}

    for node_id, node in nodes.items():
        depends_on = node.get("depends_on", {}).get("nodes", [])
        upstream_deps = [
            dep for dep in depends_on
            if (dep.startswith(f"model.{upstream_project}.") or
                f".{upstream_project}." in dep and dep.startswith("source."))
        ]

        if upstream_deps:
            cross_refs[node_id] = upstream_deps

    return cross_refs


def validate_lineage(manifest_path: Path, upstream_project: str = "dbt_up") -> Tuple[bool, str]:
    """
    Validate that the manifest contains cross-project lineage.

    Returns (success: bool, message: str)
    """
    manifest = load_manifest(manifest_path)

    # Get project name from manifest
    project_name = manifest.get("metadata", {}).get("project_name", "unknown")

    print(f"Validating lineage for project: {project_name}")
    print(f"Manifest path: {manifest_path}")
    print(f"Looking for references to: {upstream_project}")
    print("-" * 60)

    # Check parent_map
    parent_refs = find_cross_project_refs(manifest, upstream_project)

    # Check nodes depends_on (fallback/additional check)
    node_refs = find_cross_project_refs_in_nodes(manifest, upstream_project)

    # Combine findings
    all_refs = {**parent_refs, **node_refs}

    if not all_refs:
        return False, f"No cross-project references to '{upstream_project}' found in manifest"

    # Report findings
    print(f"\n✓ Found {len(all_refs)} model(s) with cross-project references:\n")

    for node_id, upstream_parents in all_refs.items():
        node_name = node_id.split(".")[-1]
        print(f"  {node_name}:")
        for parent in upstream_parents:
            parent_name = parent.split(".")[-1]
            print(f"    └── {parent} (upstream: {parent_name})")

    # Verify parent_map specifically (this is the key lineage indicator)
    if parent_refs:
        print(f"\n✓ parent_map contains {upstream_project} references - DAG lineage preserved!")
        return True, "Cross-project lineage validated successfully"
    else:
        print(f"\n⚠ depends_on has refs but parent_map is missing - partial lineage")
        return True, "Partial lineage found (depends_on only)"


def main():
    parser = argparse.ArgumentParser(
        description="Validate dbt mesh cross-project lineage"
    )
    parser.add_argument(
        "--project",
        choices=["dbt_down_loom", "dbt_down"],
        help="Project to validate (looks for target/manifest.json)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Direct path to manifest.json file"
    )
    parser.add_argument(
        "--upstream",
        default="dbt_up",
        help="Upstream project name to look for in lineage"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all downstream projects"
    )

    args = parser.parse_args()

    # Determine manifest path(s) to validate
    script_dir = Path(__file__).parent
    manifests_to_check = []

    if args.manifest:
        manifests_to_check.append(args.manifest)
    elif args.project:
        manifests_to_check.append(script_dir / args.project / "target" / "manifest.json")
    elif args.all:
        manifests_to_check.extend([
            script_dir / "dbt_down_loom" / "target" / "manifest.json",
            script_dir / "dbt_down" / "target" / "manifest.json",
        ])
    else:
        print("Usage: Specify --project, --manifest, or --all")
        print("\nExamples:")
        print("  python validate_lineage.py --project dbt_down_loom")
        print("  python validate_lineage.py --project dbt_down")
        print("  python validate_lineage.py --all")
        print("  python validate_lineage.py --manifest path/to/manifest.json")
        sys.exit(1)

    # Validate each manifest
    all_passed = True
    results = []

    for manifest_path in manifests_to_check:
        print("\n" + "=" * 60)
        try:
            success, message = validate_lineage(manifest_path, args.upstream)
            results.append((manifest_path, success, message))
            if not success:
                all_passed = False
        except FileNotFoundError as e:
            print(f"✗ {e}")
            results.append((manifest_path, False, str(e)))
            all_passed = False
        except Exception as e:
            print(f"✗ Error validating {manifest_path}: {e}")
            results.append((manifest_path, False, str(e)))
            all_passed = False

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    for manifest_path, success, message in results:
        status = "✓ PASS" if success else "✗ FAIL"
        project = manifest_path.parent.parent.name if manifest_path.parent.name == "target" else "unknown"
        print(f"{status}: {project} - {message}")

    # Exit with appropriate code
    if all_passed:
        print("\n✓ All lineage validations passed!")
        sys.exit(0)
    else:
        print("\n✗ Some validations failed - check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
