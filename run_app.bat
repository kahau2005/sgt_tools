@echo off
set "PYTHON_EXE=C:\Users\pmhau\AppData\Local\Programs\Python\Python310\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Khong tim thay Python 3.10 tai:
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import selenium" >nul 2>&1
if errorlevel 1 (
    echo Dang cai Selenium vao dung Python cua ung dung...
    "%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo Cai Selenium that bai.
        pause
        exit /b 1
    )
)

cd /d "%~dp0"
"%PYTHON_EXE%" main.py
if errorlevel 1 pause
