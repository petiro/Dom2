"""
Utility functions for PyInstaller compatibility and resource management
"""
import sys
import os


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    
    Args:
        relative_path: Path relative to the project root
        
    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not frozen, use the project root (parent of core/)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(base_path, relative_path)


def ensure_directory(directory_path):
    """
    Ensure a directory exists, create it if it doesn't
    
    Args:
        directory_path: Path to the directory
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)
