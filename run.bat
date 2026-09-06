@echo off
chcp 65001 >nul
title AutoScanText - OCR Ban Ve Ky Thuat va Dung Sai

cd /d "%~dp0"

echo ======================================================================
echo          AUTOSCANTEXT - HE THONG OCR BAN VE KY THUAT
echo ======================================================================
echo  [+] Dang tim kiem moi truong Python tren may...

set "PYTHON_EXE="

:: 1. Kiem tra Python 3.12 trong LocalAppData (vi tri chuan tren may)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

:: 2. Kiem tra Python 3.11 trong LocalAppData neu chua tim thay
if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    )
)

:: 3. Quet bat ky phien ban Python nao trong LocalAppData
if not defined PYTHON_EXE (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" set "PYTHON_EXE=%%D\python.exe"
    )
)

:: 4. Thu lay duong dan tu lenh where python
if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE (
            echo %%i | findstr /i "WindowsApps" >nul
            if errorlevel 1 (
                set "PYTHON_EXE=%%i"
            )
        )
    )
)

:: 5. Fallback cuoi cung
if not defined PYTHON_EXE (
    set "PYTHON_EXE=python"
)

:: Lay thu muc Python va them vao PATH tam thoi
for %%F in ("%PYTHON_EXE%") do set "PY_DIR=%%~dpF"
if exist "%PY_DIR%" (
    set "PATH=%PY_DIR%;%PY_DIR%Scripts;%PATH%"
)

echo  [+] Duong dan Python: %PYTHON_EXE%
echo  [+] Dang khoi dong Web Server tai: http://localhost:8000
echo  [+] Trinh duyet se tu dong mo len sau 2 giay...
echo  [+] De dung server: Nhan Ctrl + C
echo ======================================================================

:: Tu dong giai phong port 8000 neu server cu dang chay ngam
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo  [*] Phat hien server cu dang chiem cong 8000 ^(PID: %%p^), dang giai phong...
    taskkill /F /PID %%p >nul 2>&1
)

:: Hen gio mo trinh duyet sau khi uvicorn khoi dong
start "" /b cmd /c "ping 127.0.0.1 -n 3 >nul & start http://localhost:8000"

"%PYTHON_EXE%" app.py

pause
