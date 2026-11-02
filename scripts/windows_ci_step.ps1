param(
    [Parameter(Mandatory=$true)][string]$StepName,
    [Parameter(Mandatory=$true)][string]$Executable,
    [string[]]$Arguments = @()
)
$ErrorActionPreference = 'Stop'
$rankLog = Join-Path $env:RUNNER_TEMP ('rank-ci-' + [guid]::NewGuid().ToString('N') + '.log')
$rankExit = 1
try {
    & $Executable @Arguments 2>&1 | Tee-Object -FilePath $rankLog
    $rankExit = $LASTEXITCODE
} catch {
    $_.Exception.Message | Add-Content -LiteralPath $rankLog
}
if ($rankExit -ne 0) {
    $rankLines = @(Get-Content -LiteralPath $rankLog | Where-Object { $_ -match '(?i)error|failed|exception|cannot|not found|\.mjs:\d+|\.ps1:\d+' } | Select-Object -Last 8)
    if (-not $rankLines.Count) { $rankLines = @("$StepName failed with exit code $rankExit.") }
    $rankSecrets = @(Get-ChildItem Env: | Where-Object { $_.Name -match '(?i)TOKEN|SECRET|PASSWORD|API_KEY|CSC_LINK' } | Where-Object { $_.Value.Length -gt 5 })
    foreach ($rankLine in $rankLines) {
        $rankSafe = [string]$rankLine
        foreach ($rankSecret in $rankSecrets) { $rankSafe = $rankSafe.Replace($rankSecret.Value, '***') }
        $rankSafe = $rankSafe.Substring(0, [Math]::Min(1500, $rankSafe.Length)).Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
        Write-Output ('::error title=' + $StepName + '::' + $rankSafe)
    }
}
exit $rankExit
