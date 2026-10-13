$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = "C:\HAU\Internship\Task\Sub_Check\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Khong tim thay Python environment: $pythonExe"
}

$pyinstallerArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noconsole",
    "--name", "GBSubmit",
    "--paths", $projectDir,
    "--hidden-import", "selenium.webdriver.firefox.webdriver",
    "--hidden-import", "selenium.webdriver.firefox.options",
    "--hidden-import", "selenium.webdriver.firefox.service",
    "--add-data", "$(Join-Path $projectDir 'geckodriver.exe')`:.",
    (Join-Path $projectDir "main.py")
)
& $pythonExe @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller that bai."
}

Write-Host "Build thanh cong:"
Write-Host (Join-Path $projectDir "dist\GBSubmit\GBSubmit.exe")
