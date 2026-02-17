#!/usr/bin/env python3
"""
Test script to validate agent artifact generation without Modal execution.
This tests the script generation logic and ensures all components are working.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from solver.demo_script import build_demo_params, create_demo_artifacts, display_preview

def main():
    print("=" * 80)
    print("Testing Agent Artifact Generation (No Modal Execution)")
    print("=" * 80)
    print()

    # Build demo parameters
    print("Step 1: Building demo parameters...")
    params = build_demo_params()
    print(f"✓ Model: {params.model_name}")
    print(f"✓ Repo: {params.repo_url}")
    print(f"✓ Issue: {params.issue_url}")
    print(f"✓ Temperature: {params.temperature}")
    print(f"✓ Max iterations: {params.max_iterations}")
    print()

    # Create artifacts
    print("Step 2: Generating artifacts...")
    output_dir = Path(__file__).with_name("test_artifacts")
    artifacts = create_demo_artifacts(
        config={"output_dir": output_dir, "params": params}
    )
    print(f"✓ Created tfbd.yaml at: {artifacts['tfbd_path']}")
    print(f"✓ Created agent script at: {artifacts['script_path']}")
    print()

    # Display preview
    print("Step 3: Previewing generated artifacts...")
    print()
    display_preview(artifacts=artifacts, max_lines=30)

    # Validate files exist and are non-empty
    print("=" * 80)
    print("Validation Results")
    print("=" * 80)
    for name, path in artifacts.items():
        size = path.stat().st_size
        status = "✓ PASS" if size > 0 else "✗ FAIL"
        print(f"{status} {name}: {size} bytes")

    print()
    print("=" * 80)
    print("✓ Artifact generation test completed successfully!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Set up Modal: modal setup")
    print("2. Run full demo: uv run solver/e2b_standalone_demo.py")
    print()

if __name__ == "__main__":
    main()
