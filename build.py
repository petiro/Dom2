#!/usr/bin/env python3
"""
SuperAgent Build Script
Cross-platform: builds correctly on both Windows and Linux.
Uses the real Chrome browser (no Playwright drivers bundled = lighter exe).
"""
import subprocess
import sys
import os
import shutil
import platform


def main():
    print("=" * 60)
    print("  SuperAgent - Build Standalone Executable")
    print("=" * 60)

    is_windows = platform.system() == "Windows"
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

    # Platform-specific settings
    separator = ";" if is_windows else ":"
    exe_name = "SuperAgent"

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
        "--onefile",
        "--name", exe_name,
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "yaml",
        "--hidden-import", "requests",
        "--hidden-import", "ui.desktop_app",
        "--hidden-import", "ui.telegram_tab",
        "--hidden-import", "ai.vision_learner",
        "--hidden-import", "ai.rpa_healer",
        "--hidden-import", "ai.telegram_learner",
        "--hidden-import", "core.utils",
        "--hidden-import", "core.dom_executor_playwright",
        "--hidden-import", "core.dom_scanner",
        "--hidden-import", "gateway.telegram_parser_fixed",
        "--hidden-import", "gateway.pattern_memory",
        "--hidden-import", "gateway.telegram_listener_fixed",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "playwright._impl._api_types",
        f"--add-data=config{separator}config",
        f"--add-data=ai{separator}ai",
        f"--add-data=core{separator}core",
        f"--add-data=ui{separator}ui",
        f"--add-data=gateway{separator}gateway",
        "--exclude-module", "cryptography",
        "--exclude-module", "playwright.driver",
        "--noconfirm",
        "--clean",
    ]

    if is_windows:
        cmd.append("--noconsole")
    else:
        cmd.append("--strip")

    print(f"\nPlatform: {platform.system()}")
    print(f"Python: {sys.version}")
    print("Building single-file executable...\n")

    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode != 0:
        print("\nBuild FAILED!")
        sys.exit(1)

    # Find the executable (handle .exe on Windows)
    extension = ".exe" if is_windows else ""
    exe_filename = f"{exe_name}{extension}"
    exe_path = os.path.join(project_dir, "dist", exe_filename)

    if not os.path.isfile(exe_path):
        print(f"\nBuild completed but executable not found: {exe_path}")
        # Try to find what was created
        dist_dir = os.path.join(project_dir, "dist")
        if os.path.exists(dist_dir):
            print("Files in dist/:")
            for f in os.listdir(dist_dir):
                print(f"  {f}")
        sys.exit(1)

    exe_size = os.path.getsize(exe_path) / (1024 * 1024)

    # Create installer package
    print("\nCreating installer package...")
    pkg_dir = os.path.join(project_dir, "dist", "SuperAgent-Installer")
    os.makedirs(pkg_dir, exist_ok=True)

    # Copy executable
    shutil.copy2(exe_path, os.path.join(pkg_dir, exe_filename))

    # Copy config
    config_dir = os.path.join(pkg_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    for config_file in ["config.yaml", "selectors.yaml"]:
        src = os.path.join(project_dir, "config", config_file)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(config_dir, config_file))

    # Create runtime dirs
    for d in ["logs", "data"]:
        os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

    if is_windows:
        # Windows: create zip
        archive_path = os.path.join(project_dir, "dist", "SuperAgent-Installer")
        shutil.make_archive(archive_path, "zip",
                            os.path.join(project_dir, "dist"), "SuperAgent-Installer")
        archive_name = "SuperAgent-Installer.zip"
    else:
        # Linux: create tar.gz + include install.sh
        installer_src = os.path.join(project_dir, "install.sh")
        if os.path.exists(installer_src):
            shutil.copy2(installer_src, os.path.join(pkg_dir, "install.sh"))

        archive_path = os.path.join(project_dir, "dist", "SuperAgent-Installer")
        shutil.make_archive(archive_path, "gztar",
                            os.path.join(project_dir, "dist"), "SuperAgent-Installer")
        archive_name = "SuperAgent-Installer.tar.gz"

    print("\n" + "=" * 60)
    print("  BUILD SUCCESSFUL!")
    print(f"  Platform:    {platform.system()}")
    print(f"  Executable:  dist/{exe_filename} ({exe_size:.1f} MB)")
    print(f"  Installer:   dist/{archive_name}")
    print("=" * 60)

    if is_windows:
        print(f"\nTo run: dist\\{exe_filename}")
        print("NOTE: Close Chrome before starting SuperAgent!")
    else:
        print("\nTo install:")
        print("  tar xzf dist/SuperAgent-Installer.tar.gz")
        print("  cd SuperAgent-Installer && ./install.sh")


if __name__ == "__main__":
    main()
