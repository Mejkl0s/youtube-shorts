$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'

try {
    Write-Host 'Rank Studio - vizualni AI zdarma na tomto pocitaci'
    Write-Host 'Bez API klice a bez poplatku za model. Prvni priprava stahne nekolik GB.'
    $rankRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
    Write-Host "Pamet pocitace: $rankRamGB GB. Doporuceno 16 GB a vice; na CPU muze byt vyber pomaly."
    if ($rankRamGB -lt 7.5) { throw 'Pro tento vizualni model je potreba alespon 8 GB RAM. Bezne hledani a rucni strih zustavaji zdarma.' }
    $rankModelDirectory = $env:OLLAMA_MODELS
    if (-not $rankModelDirectory) { $rankModelDirectory = Join-Path $env:USERPROFILE '.ollama\models' }
    $rankDrive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($rankModelDirectory))
    if ($rankDrive.AvailableFreeSpace -lt 8GB) { throw 'Pro instalaci a model uvolni alespon 8 GB na disku s modely Ollama.' }
    $rankOllama = Get-Command ollama.exe -ErrorAction SilentlyContinue
    $rankKnownPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (-not $rankOllama -and (Test-Path -LiteralPath $rankKnownPath)) { $rankOllama = Get-Item -LiteralPath $rankKnownPath }
    if (-not $rankOllama) {
        $rankWinget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $rankWinget) { throw 'Chybi winget. Nainstaluj App Installer z Microsoft Store a spust pripravu znovu.' }
        Write-Host 'Instaluji Ollama.Ollama z oficialniho katalogu winget...'
        & $rankWinget.Source install --id Ollama.Ollama --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) { throw 'Instalace Ollama selhala. Precti zpravu instalatoru a spust pripravu znovu.' }
        $rankMachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $rankUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $env:Path = "$rankMachinePath;$rankUserPath;$env:Path"
        $rankOllama = Get-Command ollama.exe -ErrorAction SilentlyContinue
        if (-not $rankOllama -and (Test-Path -LiteralPath $rankKnownPath)) { $rankOllama = Get-Item -LiteralPath $rankKnownPath }
        if (-not $rankOllama) { throw 'Ollama neni dostupna. Zavri a znovu spust studio a pripravu AI.' }
    }
    $rankExecutable = $rankOllama.Source
    if (-not $rankExecutable) { $rankExecutable = $rankOllama.FullName }
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $rankServing = $false
    try {
        $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        $rankServing = $true
    } catch {}
    if (-not $rankServing) {
        Write-Host 'Spoustim lokalni sluzbu Ollama...'
        Start-Process -FilePath $rankExecutable -ArgumentList 'serve' -WindowStyle Minimized
        for ($rankAttempt = 0; $rankAttempt -lt 30; $rankAttempt++) {
            Start-Sleep -Seconds 1
            try {
                $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 1
                $rankServing = $true
                break
            } catch {}
        }
    }
    if (-not $rankServing) { throw 'Ollama se nespustila na 127.0.0.1:11434. Zkontroluj jeji okno.' }
    Write-Host 'Stahuji qwen2.5vl:3b. Toto je jednorazove stazeni; prubeh uvidis nize.'
    & $rankExecutable pull 'qwen2.5vl:3b'
    if ($LASTEXITCODE -ne 0) { throw 'Model se nepodarilo stahnout. Zkontroluj pripojeni a spust pripravu znovu; hotove casti stahovani se vyuziji.' }
    Write-Host 'Hotovo. Ve studiu klikni Overit AI a vyber AI na mem PC - zdarma.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $null = Read-Host 'Pro zavreni stiskni Enter'
    exit 1
}
$null = Read-Host 'Pro zavreni stiskni Enter'
