param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Refresh-ToolPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath;$env:Path"
    $ocrDirectory = Join-Path $env:ProgramFiles 'Tesseract-OCR'
    if (Test-Path (Join-Path $ocrDirectory 'tesseract.exe')) {
        $env:Path = "$ocrDirectory;$env:Path"
    }
}

function Find-StudioPython {
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $version = & $pyLauncher.Source -3.12 -c 'import sys; print(sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq 'True') {
                return @{Executable=$pyLauncher.Source; Prefix=@('-3.12')}
            }
        } catch {}
    }
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:ProgramFiles 'Python312\python.exe')
    )) {
        if (Test-Path $candidate) {
            try {
                $version = & $candidate -c 'import sys; print(sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32)' 2>$null
                if ($LASTEXITCODE -eq 0 -and $version -eq 'True') {
                    return @{Executable=$candidate; Prefix=@()}
                }
            } catch {}
        }
    }
    return $null
}

function Install-StudioTool([string]$PackageId) {
    $wingetCommand = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $wingetCommand) {
        throw 'Chybi winget. Nainstalujte App Installer z Microsoft Store, pak spustte tento soubor znovu. Podrobnosti jsou ve WINDOWS.md.'
    }
    Write-Host "Instaluji $PackageId z oficialniho katalogu winget..."
    & $wingetCommand.Source install --id $PackageId --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
        throw "Instalace $PackageId selhala (kod $LASTEXITCODE). Dokoncete ji a spustte studio znovu."
    }
    Refresh-ToolPath
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'Tento spoustec potrebuje Windows 10/11 x64.'
    }
    $machineArchitecture = $env:PROCESSOR_ARCHITEW6432
    if (-not $machineArchitecture) { $machineArchitecture = $env:PROCESSOR_ARCHITECTURE }
    if ($machineArchitecture -ne 'AMD64') {
        throw 'Tento spoustec je urcen pro Windows x64; tato konfigurace nepodporuje ARM ani 32bitovy Windows.'
    }
    $projectDirectory = Split-Path -Parent $PSScriptRoot
    Set-Location -LiteralPath $projectDirectory
    if (-not (Test-Path 'requirements.txt') -or -not (Test-Path 'backend\fonts\DejaVuSans-Bold.ttf')) {
        throw 'Nejprve rozbalte cely ZIP pomoci Extrahovat vse. Nespoustejte soubor primo uvnitr ZIPu.'
    }
    Write-Host 'Rank Studio pro tento pocitac. Prvni instalace muze trvat nekolik minut.'
    Write-Host 'Chybejici Python 3.12, Node.js a FFmpeg se nainstaluji pomoci winget.'
    Refresh-ToolPath
    $studioPython = Find-StudioPython
    if (-not $studioPython) {
        Install-StudioTool 'Python.Python.3.12'
        $studioPython = Find-StudioPython
        if (-not $studioPython) { throw 'Python 3.12 x64 neni dostupny. Zavrete okno a spustte studio znovu.' }
    }
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    $nodeReady = $false
    if ($nodeCommand) {
        $nodeMajor = & $nodeCommand.Source -p "Number(process.versions.node.split('.')[0])"
        $nodeReady = $LASTEXITCODE -eq 0 -and [int]$nodeMajor -ge 24
    }
    if (-not $nodeReady) { Install-StudioTool 'OpenJS.NodeJS.LTS' }
    if (-not (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe.exe -ErrorAction SilentlyContinue)) {
        Install-StudioTool 'Gyan.FFmpeg'
    }
    if (-not (Get-Command tesseract.exe -ErrorAction SilentlyContinue)) {
        Write-Host 'Pridavam take Tesseract pro bezplatne rozpoznani predlohy.'
        try { Install-StudioTool 'UB-Mannheim.TesseractOCR' }
        catch { Write-Warning 'Tesseract se nepodarilo nainstalovat. Ranking a export lze pouzit; vzhled nastavite rucne.' }
    }
    $env:PYTHONUTF8 = '1'
    $pythonPrefix = $studioPython.Prefix
    $launchArguments = @((Join-Path $PSScriptRoot 'local_studio.py'))
    if ($CheckOnly) { $launchArguments += '--doctor' }
    & $studioPython.Executable @pythonPrefix @launchArguments
    exit $LASTEXITCODE
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
