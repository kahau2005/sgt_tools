$ErrorActionPreference = "Stop"

$installRoot = Join-Path $env:LOCALAPPDATA "Programs\GBSubmit"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\GB Submit"
$payload = Join-Path $PSScriptRoot "payload.zip"

if (-not (Test-Path -LiteralPath $payload -PathType Leaf)) {
    throw "Khong tim thay goi du lieu cai dat: $payload"
}

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
Expand-Archive -LiteralPath $payload -DestinationPath $installRoot -Force

$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $startMenu "GB Submit.lnk"
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installRoot "GBSubmit.exe"
$shortcut.WorkingDirectory = $installRoot
$shortcut.Description = "GB Submit - Check Link Facebook"
$shortcut.Save()

$desktop = [Environment]::GetFolderPath("Desktop")
if ($desktop) {
    $desktopShortcut = $shell.CreateShortcut(
        (Join-Path $desktop "GB Submit.lnk")
    )
    $desktopShortcut.TargetPath = Join-Path $installRoot "GBSubmit.exe"
    $desktopShortcut.WorkingDirectory = $installRoot
    $desktopShortcut.Description = "GB Submit - Check Link Facebook"
    $desktopShortcut.Save()
}

Start-Process -FilePath (Join-Path $installRoot "GBSubmit.exe")
