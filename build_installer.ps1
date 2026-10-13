$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Join-Path $projectDir "dist\GBSubmit"
$stageDir = Join-Path $projectDir "build\installer-stage"
$payloadPath = Join-Path $stageDir "payload.zip"
$installScript = Join-Path $stageDir "install_payload.ps1"
$sedPath = Join-Path $stageDir "GBSubmit-Setup.sed"
$installerPath = Join-Path $projectDir "dist\GBSubmit-Setup.exe"
$iexpress = Join-Path $env:WINDIR "System32\iexpress.exe"

if (-not (Test-Path -LiteralPath (Join-Path $appDir "GBSubmit.exe") -PathType Leaf)) {
    throw "Hay build GBSubmit.exe truoc khi tao installer."
}
if (-not (Test-Path -LiteralPath $iexpress -PathType Leaf)) {
    throw "Khong tim thay IExpress: $iexpress"
}

New-Item -ItemType Directory -Path $stageDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $projectDir "install_payload.ps1") `
    -Destination $installScript -Force
Compress-Archive -Path (Join-Path $appDir "*") `
    -DestinationPath $payloadPath -CompressionLevel Optimal -Force

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=1
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$stageDir
[SourceFiles0]
%FILE0%=
%FILE1%=
[Strings]
InstallPrompt="Install GB Submit for the current Windows user?"
FinishMessage="GB Submit was installed. Shortcuts were added to Start Menu and Desktop."
TargetName=$installerPath
FriendlyName="GB Submit Setup"
AppLaunched="powershell.exe -NoProfile -ExecutionPolicy Bypass -File install_payload.ps1"
FILE0="payload.zip"
FILE1="install_payload.ps1"
"@

Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII
if (Test-Path -LiteralPath $installerPath -PathType Leaf) {
    Remove-Item -LiteralPath $installerPath -Force
}
Start-Process -FilePath $iexpress `
    -ArgumentList @("/N", "/Q", $sedPath) `
    -Wait -PassThru | Out-Null
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "IExpress khong tao ra installer: $installerPath"
}
$builtInstaller = Get-Item -LiteralPath $installerPath
if ($builtInstaller.Length -lt 1MB) {
    throw "Installer co kich thuoc bat thuong: $($builtInstaller.Length) bytes"
}

Write-Host "Installer build thanh cong: $($builtInstaller.FullName)"
Write-Host "Dung luong: $([math]::Round($builtInstaller.Length / 1MB, 1)) MB"
