@echo off
REM ============================================================
REM  SuperAgent V4 — Chrome Cleanup Pre-Launch
REM  Run this BEFORE starting SuperAgent_Pro.exe to ensure
REM  no zombie Chrome processes block the browser profile.
REM ============================================================

echo [SuperAgent] Cleaning up Chrome zombie processes...

REM 1. Kill all Chrome processes
taskkill /F /IM chrome.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Chrome processes terminated.
) else (
    echo [OK] No Chrome processes found.
)

REM 2. Kill any lingering chromedriver processes
taskkill /F /IM chromedriver.exe >nul 2>&1

REM 3. Wait for processes to fully terminate
timeout /t 2 /nobreak >nul

REM 4. Remove Chrome lock files (prevents "profile in use" errors)
set "CHROME_DIR=%LOCALAPPDATA%\Google\Chrome\User Data"
for %%F in (SingletonLock SingletonSocket SingletonCookie) do (
    if exist "%CHROME_DIR%\%%F" (
        del /f /q "%CHROME_DIR%\%%F" >nul 2>&1
        if not exist "%CHROME_DIR%\%%F" (
            echo [OK] Removed %%F
        ) else (
            echo [ERROR] Failed to remove %%F.
        )
    )
)

REM 5. Create required folders if missing
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "config" mkdir config

echo.
echo [SuperAgent] Cleanup complete. Safe to launch SuperAgent_Pro.exe
echo.
pause
