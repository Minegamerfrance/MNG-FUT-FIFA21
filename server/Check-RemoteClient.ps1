$ErrorActionPreference = 'Stop'
$preset = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'remote-test.json') -Raw | ConvertFrom-Json
if ($preset.gameId -ne '21') { throw 'Configuration distante incompatible.' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $command -or $command.Source -match '\\WindowsApps\\') { throw 'Lance d abord Preparer.cmd.' }
    $python = $command.Source
}
& $python (Join-Path $PSScriptRoot 'runtime-source\remote_relay.py') --remote-host ([string]$preset.host) --check
exit $LASTEXITCODE
