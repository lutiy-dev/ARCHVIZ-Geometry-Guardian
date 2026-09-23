@echo off
setlocal
title ARCHVIZ Production VARIANT 01 Installer
set "LAB=C:\ComfyUI-Installs\ARCHVIZ_LAB\ComfyUI"
set "PY=%LAB%\.venv\Scripts\python.exe"
set "HERE=%~dp0"
set "LOG=%HERE%INSTALL_VARIANT_01_LOG.txt"

echo ARCHVIZ Production VARIANT 01
echo ========================
echo.
if not exist "%PY%" (
  echo FAIL: Python not found: %PY%
  pause
  exit /b 1
)
if not exist "%HERE%install_variant_01.py" (
  echo FAIL: install_variant_01.py not found
  pause
  exit /b 1
)

"%PY%" "%HERE%install_variant_01.py" --lab "%LAB%" > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
echo.
if "%RC%"=="0" (
  echo INSTALL RESULT: PASS
) else (
  echo INSTALL RESULT: FAIL code=%RC%
)
echo.
echo Log: %LOG%
echo.
echo IMPORTANT: fully close all ComfyUI processes, then start ARCHVIZ_LAB.
echo Open exactly: ARCHVIZ_Production_VARIANT_01.json
echo.
pause
exit /b %RC%
