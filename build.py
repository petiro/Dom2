#!/usr/bin/env python3
"""
SuperAgent Build Script
Builds the executable using PyInstaller
"""
import subprocess
import sys
import os
import shutil


def main():
    print("=" * 60)
    print("  SuperAgent - Build Executable")
    print("=" * 60)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Ensure required directories exist
    os.makedirs("config", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # Clean previous builds
    for folder in ["build", "dist"]:
        path = os.path.join(project_dir, folder)
        if os.path.exists(path):
            print(f"Cleaning {folder}/...")
            shutil.rmtree(path)

    # Run PyInstaller
    print("\nBuilding executable with PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "SuperAgent.spec",
        "--noconfirm",
        "--clean",
    ]

    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode != 0:
        print("\nBuild FAILED!")
        sys.exit(1)

    # Create runtime directories in dist
    dist_dir = os.path.join(project_dir, "dist", "SuperAgent")
    if os.path.exists(dist_dir):
        for d in ["logs", "data"]:
            os.makedirs(os.path.join(dist_dir, d), exist_ok=True)

        print("\n" + "=" * 60)
        print("  BUILD SUCCESSFUL!")
        print(f"  Output: {dist_dir}")
        print("=" * 60)
    else:
        print("\nBuild completed but output directory not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
