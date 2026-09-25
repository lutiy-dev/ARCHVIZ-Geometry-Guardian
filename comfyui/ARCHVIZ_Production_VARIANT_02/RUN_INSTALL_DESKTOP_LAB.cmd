@echo off
setlocal
set "LAB=C:\ComfyUI-Installs\ARCHVIZ_LAB\ComfyUI"
set "PY=%LAB%\.venv\Scripts\python.exe"
set "SHARED=%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\input"
if not exist "%PY%" (
  echo [STOP] LAB Python not found: %PY%
  pause
  exit /b 1
)
echo [1/2] Running Variant 02 pre-install self-test...
"%PY%" "%~dp0self_test_variant_02.py"
if errorlevel 1 (
  echo [STOP] SELF_TEST failed. Nothing installed.
  pause
  exit /b 1
)
echo [2/2] Installing into ARCHVIZ_LAB...
"%PY%" "%~dp0install_variant_02.py" --lab "%LAB%" --shared-input "%SHARED%"
if errorlevel 1 (
  echo [STOP] INSTALL failed.
  pause
  exit /b 1
)
echo.
echo [PASS] ARCHVIZ Production VARIANT 02 installed.
echo Fully restart ComfyUI Desktop, then open ARCHVIZ_Production_VARIANT_02.json
pause
