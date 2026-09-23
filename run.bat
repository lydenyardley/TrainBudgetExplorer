@echo off
rem Double-click this file to run the app: it builds the site and opens it in
rem your browser at http://localhost:8741. Close the black window to stop it.
cd /d "%~dp0"
python run.py %*
if errorlevel 1 pause
