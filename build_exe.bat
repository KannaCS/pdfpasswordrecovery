@echo off
echo Building Kanna PDF Password Recovery...

REM Find Python DLL path
for /f "tokens=*" %%i in ('python -c "import sys; import os; print(os.path.dirname(sys.executable))"') do set PYTHON_DIR=%%i

echo Python directory: %PYTHON_DIR%

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist\Kanna PDF Password Recovery.exe" del "dist\Kanna PDF Password Recovery.exe"
if exist "build" rmdir /s /q build

REM Build using PyInstaller with all Python DLLs
echo Building executable...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --add-binary "%PYTHON_DIR%\python311.dll;." ^
  --add-binary "%PYTHON_DIR%\python3.dll;." ^
  --add-binary "%PYTHON_DIR%\vcruntime140.dll;." ^
  --icon=kanna_icon.ico ^
  --name "Kanna PDF Password Recovery" ^
  --add-data "kanna_icon.ico;." ^
  main.py

echo.
echo Build complete! Check the dist folder for your executable.
echo.
