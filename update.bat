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
    copy /Y SuperAgent_Pro_new.exe SuperAgent_Pro.exe
    del SuperAgent_Pro_new.exe
    echo Aggiornamento completato!
) else (
    echo ERRORE: SuperAgent_Pro_new.exe non trovato.
    echo Posiziona il nuovo exe come "SuperAgent_Pro_new.exe" e rilancia.
)

pause
