param([string]$Installer)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Installer acceptance runs only on a disposable GitHub Windows runner, not a personal Windows profile.' }
if (-not $Installer) { $Installer = (Get-ChildItem 'release\windows\*Setup.exe' | Select-Object -First 1).FullName }
if (-not $Installer -or -not (Test-Path -LiteralPath $Installer)) { throw 'Built NSIS installer not found.' }
$rankInstall = Join-Path $env:RUNNER_TEMP ('RankStudioInstalled-' + [guid]::NewGuid().ToString('N'))
$rankData = Join-Path $env:APPDATA 'Rank Studio'
$rankSentinel = Join-Path $rankData 'installer-retention-check.txt'
function Install-Rank {
    $result = Start-Process -FilePath $Installer -ArgumentList @('/S', "/D=$rankInstall") -Wait -PassThru
    if ($result.ExitCode -ne 0) { throw "Installer failed: $($result.ExitCode)" }
    if (-not (Test-Path -LiteralPath (Join-Path $rankInstall 'Rank Studio.exe'))) { throw 'Installed application missing.' }
}
Install-Rank
$rankShortcut = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\Rank Studio.lnk'
if (-not (Test-Path -LiteralPath $rankShortcut)) { throw 'Start menu shortcut missing.' }
$rankApplication = Start-Process -FilePath (Join-Path $rankInstall 'Rank Studio.exe') -PassThru
$rankDatabase = Join-Path $rankData 'runtime\private\desktop\projects.sqlite3'
$rankReady = $false
$rankProbe = @'
import sqlite3,sys
try:
 db=sqlite3.connect(sys.argv[1]);print(db.execute("SELECT count(*) FROM state WHERE key='rank-studio-project'").fetchone()[0]);db.close()
except Exception: print(0)
'@
for ($rankAttempt=0; $rankAttempt -lt 150; $rankAttempt++) {
    Start-Sleep -Milliseconds 400
    $rankApplication.Refresh()
    if ($rankApplication.HasExited) { throw 'Installed app exited during startup.' }
    if ((Test-Path -LiteralPath $rankDatabase) -and $rankApplication.MainWindowHandle -ne 0) {
        $rankCount = & python -c $rankProbe $rankDatabase
        if ($rankCount -eq '1') { $rankReady = $true; break }
    }
}
if (-not $rankReady) { throw 'Installed editor did not reach persistent, rendered state.' }
if (-not $rankApplication.CloseMainWindow()) { throw 'Installed app did not accept normal window close.' }
if (-not $rankApplication.WaitForExit(30000)) { throw 'Installed application did not shut down normally.' }
if ($rankApplication.ExitCode -ne 0) { throw 'Installed application exited with an error.' }
'retain user data across update and uninstall' | Set-Content -LiteralPath $rankSentinel -Encoding utf8
$rankBefore = (Get-FileHash -LiteralPath $rankDatabase -Algorithm SHA256).Hash
Install-Rank
if (-not (Test-Path -LiteralPath $rankSentinel) -or (Get-FileHash -LiteralPath $rankDatabase -Algorithm SHA256).Hash -ne $rankBefore) { throw 'Reinstall changed user data.' }
$rankUninstaller = Join-Path $rankInstall 'Uninstall Rank Studio.exe'
$rankResult = Start-Process -FilePath $rankUninstaller -ArgumentList '/S' -Wait -PassThru
if ($rankResult.ExitCode -ne 0) { throw 'Uninstaller failed.' }
for ($rankAttempt=0; $rankAttempt -lt 50 -and (Test-Path -LiteralPath (Join-Path $rankInstall 'Rank Studio.exe')); $rankAttempt++) { Start-Sleep -Milliseconds 200 }
if ((Test-Path -LiteralPath (Join-Path $rankInstall 'Rank Studio.exe')) -or (Test-Path -LiteralPath $rankShortcut)) { throw 'Uninstall did not remove application files/shortcut.' }
if (-not (Test-Path -LiteralPath $rankSentinel) -or -not (Test-Path -LiteralPath $rankDatabase)) { throw 'Uninstall removed user data.' }
Write-Host 'Native installer acceptance passed: install, app startup/persistence, normal shutdown, reinstall, retained data and uninstall.'
