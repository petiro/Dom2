@echo off
REM Quick Setup Script for SuperAgent (Windows)

echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                                                               ║
echo ║         🚀  SuperAgent - Quick Setup  🚀                      ║
echo ║                                                               ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Check Python
echo 📋 Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✅ Python found: %PYTHON_VERSION%
echo.

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)
echo ✅ Dependencies installed
echo.

REM Install Playwright browsers
echo 🌐 Installing Playwright browsers...
playwright install chromium
if errorlevel 1 (
    echo ⚠️ Failed to install Playwright browsers (optional)
)
echo ✅ Playwright ready
echo.

REM Create directories
echo 📁 Creating directories...
if not exist data mkdir data
if not exist logs mkdir logs
if not exist config mkdir config
echo ✅ Directories created
echo.

REM Check config
echo ⚙️ Checking configuration...
if not exist config\config.yaml (
    echo ⚠️ config\config.yaml not found
    echo Please create it or copy from config.yaml.example
) else (
    echo ✅ Configuration found
)
echo.

REM Final instructions
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                    🎉 Setup Complete! 🎉                      ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo Next steps:
echo 1. Get free API key: https://openrouter.ai/keys
echo 2. Add key to config\config.yaml
echo 3. Run: python main.py
echo.
echo 📚 See README.md for full documentation
echo.
pause
