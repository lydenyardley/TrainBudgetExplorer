@echo off
rem Double-click this file to build Grantham and Nottingham from the real fares
rem and timetable feeds and open them at http://localhost:8742. Name other
rem stations on the command line: build_stations.bat GRA NOT KGX
rem Close the black window to stop it.
cd /d "%~dp0"
python build_stations.py %*
if errorlevel 1 pause