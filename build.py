#!/usr/bin/env python3
"""
SuperAgent Build Script
Builds a standalone single-file executable and installer package
"""
import subprocess
import sys
import os
import shutil
import stat


def main():
    print("=" * 60)
    print("  SuperAgent - Build Standalone Executable")
    print("=" * 60)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Ensure required directories exist
    for d in ["config", "logs", "data"]:
        os.makedirs(d, exist_ok=True)

    # Clean previous builds
    for folder in ["build", "dist"]:
        path = os.path.join(project_dir, folder)
        if os.path.exists(path):
            print(f"Cleaning {folder}/...")
            shutil.rmtree(path)

    # Run PyInstaller (onefile mode)
    print("\nBuilding single-file executable...")
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

    exe_path = os.path.join(project_dir, "dist", "SuperAgent")
    if not os.path.isfile(exe_path):
        print("\nBuild completed but executable not found.")
        sys.exit(1)

    exe_size = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\nExecutable size: {exe_size:.1f} MB")

    # Create installer package
    print("\nCreating installer package...")
    pkg_dir = os.path.join(project_dir, "dist", "SuperAgent-Installer")
    os.makedirs(pkg_dir, exist_ok=True)

    # Copy executable
    shutil.copy2(exe_path, os.path.join(pkg_dir, "SuperAgent"))

    # Copy config
    config_dir = os.path.join(pkg_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    shutil.copy2(
        os.path.join(project_dir, "config", "config.yaml"),
        os.path.join(config_dir, "config.yaml")
    )

    # Create runtime dirs
    for d in ["logs", "data"]:
        os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

    # Copy installer script
    installer_src = os.path.join(project_dir, "install.sh")
    if os.path.exists(installer_src):
        shutil.copy2(installer_src, os.path.join(pkg_dir, "install.sh"))

    # Create tar.gz archive
    archive_path = os.path.join(project_dir, "dist", "SuperAgent-Installer")
    shutil.make_archive(archive_path, "gztar", os.path.join(project_dir, "dist"), "SuperAgent-Installer")

    print("\n" + "=" * 60)
    print("  BUILD SUCCESSFUL!")
    print(f"  Executable:  dist/SuperAgent ({exe_size:.1f} MB)")
    print(f"  Installer:   dist/SuperAgent-Installer.tar.gz")
    print("=" * 60)
    print("\nTo install, run:")
    print("  tar xzf dist/SuperAgent-Installer.tar.gz")
    print("  cd SuperAgent-Installer && ./install.sh")


if __name__ == "__main__":
    main()
