@echo off
title SuperAgent Update
cd /d %~dp0

echo ===============================
echo   SUPERAGENT - AGGIORNAMENTO
echo ===============================

echo Arresto SuperAgent in corso...
taskkill /f /im SuperAgent_Pro.exe >nul 2>&1
timeout /t 2 /nobreak >nul

if exist SuperAgent_Pro_new.exe (
    echo Sostituzione eseguibile...
    if exist SuperAgent_Pro.exe (
        ren SuperAgent_Pro.exe SuperAgent_Pro.exe.bak
    )
    ren SuperAgent_Pro_new.exe SuperAgent_Pro.exe
    
    if errorlevel 1 (
        echo ERRORE: Aggiornamento fallito. Ripristino backup...
        if exist SuperAgent_Pro.exe.bak (
            ren SuperAgent_Pro.exe.bak SuperAgent_Pro.exe
        )
    ) else (
        echo Aggiornamento completato!
        if exist SuperAgent_Pro.exe.bak (
            del SuperAgent_Pro.exe.bak
        )
    )
) else (
    echo ERRORE: SuperAgent_Pro_new.exe non trovato.
)

pause
