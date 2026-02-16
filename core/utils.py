"""
Utility functions for PyInstaller compatibility and resource management.
"""
import sys
import os

# Shared application constants
CURRENCY_SYMBOL = "€"


def get_project_root():
    """Get absolute path to project root, works for dev and PyInstaller.
    Note: also available in config_paths.py (Path version). This version returns str."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except (NameError, TypeError, OSError):
        return os.getcwd()


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def ensure_directory(directory_path):
    """Ensure a directory exists, create it if it doesn't."""
    os.makedirs(directory_path, exist_ok=True)
