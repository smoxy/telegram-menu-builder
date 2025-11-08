#!/usr/bin/env python
"""
Upload script for PyPI publication with best practices.

Usage:
    python upload_to_pypi.py [--test] [--token TOKEN]

Options:
    --test          Upload to TestPyPI instead of PyPI
    --token TOKEN   Use inline token instead of .pypirc
    --skip-check    Skip twine check validation
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a shell command and print status."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(e.stderr)
        return False


def main():
    """Main upload function."""
    test_mode = "--test" in sys.argv
    skip_check = "--skip-check" in sys.argv
    token = None
    
    # Check for token argument
    for i, arg in enumerate(sys.argv):
        if arg == "--token" and i + 1 < len(sys.argv):
            token = sys.argv[i + 1]
            break
    
    print("\n🚀 Telegram Menu Builder - PyPI Upload")
    print(f"{'='*60}")
    print(f"Target: {'TestPyPI' if test_mode else 'PyPI'}")
    print(f"{'='*60}\n")
    
    # Step 1: Check dist folder
    dist_path = Path("dist")
    if not dist_path.exists():
        print("❌ dist/ folder not found. Run 'python -m build' first.")
        sys.exit(1)
    
    files = list(dist_path.glob("*.whl")) + list(dist_path.glob("*.tar.gz"))
    if not files:
        print("❌ No distribution files found in dist/")
        sys.exit(1)
    
    print(f"✅ Found {len(files)} distribution file(s):")
    for f in files:
        print(f"   - {f.name}")
    
    # Step 2: Verify with twine
    if not skip_check:
        if not run_command(
            ["twine", "check", "dist/*"],
            "Verifying distribution with twine"
        ):
            print("❌ Twine verification failed")
            sys.exit(1)
        print("✅ Twine check PASSED")
    
    # Step 3: Prepare upload command
    cmd = ["twine", "upload"]
    
    if test_mode:
        cmd.extend(["--repository", "testpypi"])
    
    if token:
        cmd.extend(["-u", "__token__", "-p", token])
    
    cmd.extend([f"dist/{f.name}" for f in files])
    
    # Step 4: Upload
    if run_command(cmd, f"Uploading to {'TestPyPI' if test_mode else 'PyPI'}"):
        print("\n✅ Upload completed successfully!")
        print("\n📦 Package URL:")
        if test_mode:
            print("   https://test.pypi.org/project/telegram-menu-builder/")
        else:
            print("   https://pypi.org/project/telegram-menu-builder/")
        
        print("\n📥 Install with:")
        if test_mode:
            print("   pip install -i https://test.pypi.org/simple/ telegram-menu-builder")
        else:
            print("   pip install telegram-menu-builder")
    else:
        print("\n❌ Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
