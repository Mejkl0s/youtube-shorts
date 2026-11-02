@echo off
setlocal
set "RANK_UPDATE_FOLDER=%~dp0"
echo Rank Studio - aktualizace existujici kopie
echo Nejdrive uloz projekt ve studiu a ukonci jeho cerne okno pomoci Ctrl+C.
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $stage=$null; try { $studioRoot=$env:RANK_UPDATE_FOLDER; if(-not (Test-Path -LiteralPath (Join-Path $studioRoot 'SPUSTIT-WINDOWS.bat'))) { $studioRoot=Join-Path $env:USERPROFILE 'Downloads\youtube-shorts-main (1)\youtube-shorts-main' }; $python=Join-Path $studioRoot '.venv\Scripts\python.exe'; if(-not (Test-Path -LiteralPath $python)) { throw 'Nenasel jsem existujici studio. Uloz tento BAT vedle SPUSTIT-WINDOWS.bat a spust jej znovu.' }; Write-Host ('Aktualizuji: '+$studioRoot); $stage=Join-Path ([IO.Path]::GetTempPath()) ('rank-update-'+[Guid]::NewGuid().ToString('N')); [void][IO.Directory]::CreateDirectory($stage); $helper=Join-Path $stage 'update_local.py'; Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/Mejkl0s/youtube-shorts/dad9d05e757d0ccea216e65dfbb29e71529ee9c7/scripts/update_local.py' -OutFile $helper; if((Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash -ne 'e7d4b11c72cbc5c9b5c025ad396c33b07d36fefb828fb43b080fe427d7bfb72b') { throw 'Nesouhlasi kontrolni soucet aktualizace. Aplikace nebyla zmenena.' }; & $python $helper --root $studioRoot --ref 'dad9d05e757d0ccea216e65dfbb29e71529ee9c7'; if($LASTEXITCODE -ne 0) { throw 'Aktualizace se zastavila. Precti zpravu vyse.' } } catch { Write-Host $_.Exception.Message; exit 1 } finally { if($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force } }; Write-Host 'Hotovo. Spoustim studio...'; & (Join-Path $studioRoot 'SPUSTIT-WINDOWS.bat'); exit $LASTEXITCODE"
if errorlevel 1 (
  echo Aktualizace nebo spusteni se nezadarilo. Chyba je uvedena vyse.
)
pause
