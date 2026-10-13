@echo off
setlocal
set "PROJECT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%build_exe.ps1"
if errorlevel 1 (
    echo Build that bai.
    pause
    exit /b 1
)
echo Build thanh cong:
echo %PROJECT_DIR%dist\GBSubmit\GBSubmit.exe
pause
