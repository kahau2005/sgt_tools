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
SourceFiles0=C:\HAU\Internship\Task\Sub_Check\Sub_Check\build\installer-stage
[SourceFiles0]
%FILE0%=
%FILE1%=
[Strings]
InstallPrompt="Install GB Submit for the current Windows user?"
FinishMessage="GB Submit was installed. Shortcuts were added to Start Menu and Desktop."
TargetName=C:\HAU\Internship\Task\Sub_Check\Sub_Check\dist\GBSubmit-Setup.exe
FriendlyName="GB Submit Setup"
AppLaunched="powershell.exe -NoProfile -ExecutionPolicy Bypass -File install_payload.ps1"
FILE0="payload.zip"
FILE1="install_payload.ps1"
