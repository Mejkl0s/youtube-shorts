param([ValidateSet('qwen2.5vl:3b', 'qwen2.5vl:7b')][string]$Model = 'qwen2.5vl:7b')

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'

try {
    Write-Host 'Rank Studio - vizualni AI zdarma na tomto pocitaci'
    Write-Host 'Bez API klice a bez poplatku za model. Prvni priprava stahne nekolik GB.'
    $rankRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
    Write-Host "Vybrany model: $Model. Pamet pocitace: $rankRamGB GB."
    $rankMinimumRam = 7.5
    $rankDiskSpace = 8GB
    if ($Model -eq 'qwen2.5vl:7b') {
        $rankMinimumRam = 15.5
        $rankDiskSpace = 12GB
        Write-Host 'Pro 7B doporuceno 32 GB RAM. Na grafice s 8 GB VRAM muze cast modelu bezet pres RAM a vyber bude pomalejsi.'
    } else { Write-Host 'Pro 3B doporuceno 16 GB RAM. Mensi model muze byt rychlejsi.' }
    if ($rankRamGB -lt $rankMinimumRam) { throw 'Pro vybrany model je malo RAM: 3B potrebuje alespon 8 GB, 7B alespon 16 GB. Ve studiu muzes zvolit 3B.' }
    $rankModelDirectory = $env:OLLAMA_MODELS
    if (-not $rankModelDirectory) { $rankModelDirectory = Join-Path $env:USERPROFILE '.ollama\models' }
    $rankDrive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($rankModelDirectory))
    if ($rankDrive.AvailableFreeSpace -lt $rankDiskSpace) { throw 'Pro instalaci a model uvolni misto na disku s modely Ollama: 8 GB pro 3B, 12 GB pro 7B.' }
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
    Write-Host "Stahuji $Model. Toto je jednorazove stazeni; prubeh uvidis nize."
    & $rankExecutable pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Model se nepodarilo stahnout. Zkontroluj pripojeni a spust pripravu znovu; hotove casti stahovani se vyuziji.' }
    Write-Host 'Hotovo. Ve studiu klikni Overit AI a vyber AI na mem PC - zdarma.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $null = Read-Host 'Pro zavreni stiskni Enter'
    exit 1
}
$null = Read-Host 'Pro zavreni stiskni Enter'
