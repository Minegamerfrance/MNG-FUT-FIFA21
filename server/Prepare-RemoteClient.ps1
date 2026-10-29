param([switch]$AccountMode)
$ErrorActionPreference = 'Stop'
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python -or $python.Source -match '\\WindowsApps\\') { throw 'Installe Python 3.13 ou plus recent, puis relance cette preparation.' }
$environment = Join-Path $PSScriptRoot '.venv'
$localPython = Join-Path $environment 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $localPython)) {
    & $python.Source -m venv $environment
    if ($LASTEXITCODE -ne 0) { throw 'Impossible de preparer Python dans ce dossier.' }
}
& $localPython -m pip install 'cryptography>=42'
if ($LASTEXITCODE -ne 0) { throw 'Installation de la dependance incomplete.' }
if ($AccountMode) { Write-Host 'Preparation terminee. La connexion utilise le compte MNG, sans Tailscale.' }
else { Write-Host 'Preparation terminee. Connecte Tailscale puis ouvre Connexion-serveur.cmd.' }
