@echo off
cls

echo ==============================================
echo   Attendance Report System v2.0
echo   ZKTeco MB10-VL
echo ==============================================
echo.

:: Step 1 - Fetch from device
echo [1/3] Connecting to ZKTeco device...
echo.

if not exist "fetcher\bin\ZKFetcher.exe" (
    echo [ERROR] ZKFetcher.exe not found
    echo         See SETUP.md for build instructions
    pause
    exit /b 1
)

fetcher\bin\ZKFetcher.exe
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to fetch data from device
    echo         Is the device connected to the network?
    echo         Check IP in fetcher\src\Program.cs
    pause
    exit /b 1
)

echo.
echo [OK] Data fetched successfully
echo.

:: Step 2 - Check Python
echo [2/3] Checking requirements...

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo         Download from: https://python.org
    pause
    exit /b 1
)

python -c "import openpyxl, pandas" >nul 2>&1
if errorlevel 1 (
    echo Installing required libraries...
    pip install openpyxl pandas --quiet
)

echo [OK] Requirements ready
echo.

:: Step 3 - Generate reports
echo [3/3] Generating Excel reports...
echo.

python process_attendance.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to process data
    pause
    exit /b 1
)

echo.
echo ==============================================
echo [DONE] Reports saved in: output\
echo ==============================================
echo.

explorer output
pause