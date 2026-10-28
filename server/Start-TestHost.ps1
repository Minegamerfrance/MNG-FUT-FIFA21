[CmdletBinding()]
param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'MNG21\HostingTest21'
[IO.Directory]::CreateDirectory($root) | Out-Null
$pidFile = Join-Path $root 'host.json'
$signal = Join-Path $root 'stop.signal'
$script = Join-Path $PSScriptRoot 'runtime-source\private_test_host.py'
$existing = $null
if (Test-Path -LiteralPath $pidFile) {
    $tracked = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$tracked.pid)" -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.CommandLine -and
        $candidate.CommandLine.Contains($script) -and
        ([DateTime]$candidate.CreationDate).ToUniversalTime().ToString('o') -eq [string]$tracked.created) {
        $existing = $candidate
    }
}
if ($Stop) {
    if ($existing) {
        [IO.File]::WriteAllText($signal,'stop')
        Wait-Process -Id $existing.ProcessId -Timeout 15 -ErrorAction Stop
    }
    Write-Host 'Serveur de test arrete. Club de test conserve.'
    exit 0
}
if ($existing) {
    Write-Host 'Le serveur de test est deja demarre.'
    exit 0
}
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python est requis, comme pour le serveur FIFA 21 actuel.' }
if (Test-Path -LiteralPath $signal) { Remove-Item -LiteralPath $signal }
$arguments = @('-u',('"{0}"' -f $script),'--stop-file',('"{0}"' -f $signal))
$process = Start-Process -FilePath $python.Source -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $root 'host.log') -RedirectStandardError (Join-Path $root 'host.error.log')
$created = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
@{pid=$process.Id;created=([DateTime]$created.CreationDate).ToUniversalTime().ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8
Start-Sleep -Seconds 2
if ($process.HasExited) { throw ('Le serveur ne demarre pas. Voir '+(Join-Path $root 'host.error.log')) }
Write-Host 'Serveur de test demarre sur ton reseau Tailscale prive.'
Write-Host 'Ton club habituel reste separe. Ce premier serveur possede un seul club de test.'
