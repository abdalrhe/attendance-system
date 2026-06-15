@echo off
cls

echo ==============================================
echo   Attendance Report System v3.0
echo   ZKTeco MB10-VL  (pyzk)
echo ==============================================
echo.

:: Step 1 - Check Python
echo [1/3] Checking Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo         Download from: https://python.org
    pause
    exit /b 1
)

python -c "import zk, pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Installing required libraries...
    pip install pyzk pandas openpyxl --quiet
)

echo [OK] Requirements ready
echo.

:: Step 2 - Fetch from device
echo [2/3] Connecting to ZKTeco device...
echo.

python fetch_zk.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to fetch data from device
    echo         Is the device connected to the network?
    echo         Check IP in fetch_zk.py
    pause
    exit /b 1
)

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
