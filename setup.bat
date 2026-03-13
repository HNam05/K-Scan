@echo off
:: ============================================================
:: Mae Thai - Kassenbon Scanner: Setup-Starter
:: ============================================================
:: Doppelklick auf diese Datei startet die Installation.
:: ============================================================

echo.
echo  Mae Thai - Kassenbon Scanner Setup
echo  ===================================
echo.
echo  Starte PowerShell Setup-Skript...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

pause
