@echo off
title SuperAgent Immortale Watchdog
cd /d %~dp0

echo ===============================
echo   SUPERAGENT IMMORTALE MODE
echo ===============================

:loop
echo [%date% %time%] Avvio agente...
start "" /wait SuperAgent_Pro.exe

echo [%date% %time%] Crash o chiusura rilevata
echo Restart tra 5 sec...
timeout /t 5 /nobreak >nul

goto loop
