[CmdletBinding()]
param([string]$RemoteHost='')
$ErrorActionPreference = 'Stop'
if (-not $RemoteHost -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'remote-test.json'))) {
    $preset = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'remote-test.json') -Raw | ConvertFrom-Json
    if ($preset.gameId -ne '21') { throw 'Configuration distante incompatible.' }
    $RemoteHost = [string]$preset.host
}
if (-not $RemoteHost) { $RemoteHost = Read-Host 'Adresse Tailscale du PC serveur (100.x.x.x)' }
if ($RemoteHost -notmatch '^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$') { throw 'Adresse Tailscale IPv4 attendue.' }
. (Join-Path $PSScriptRoot 'User-Settings.ps1')
$normalSettings = Get-LocalFutUserSettings (Resolve-LocalFutUserConfigRoot)
$gamePath = [string]$normalSettings.gamePath
if (-not $gamePath -or -not (Test-Path -LiteralPath $gamePath)) {
    $game = Get-Process -Name FIFA21 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($game) { $gamePath = $game.Path }
}
if (-not $gamePath -or -not (Test-Path -LiteralPath $gamePath)) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title = 'Choisir FIFA21.exe dans ton installation du jeu'
    $picker.Filter = 'FIFA 21|FIFA21.exe'
    try {
        if ($picker.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { exit 0 }
        $gamePath = $picker.FileName
    } finally { $picker.Dispose() }
}
$clientRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MNG21\RemoteClient21'
Write-Host 'Mode serveur distant prive : aucun club ne sera heberge sur ce connecteur.'
Write-Host 'Ferme le serveur FUT local avant de continuer, puis lance FIFA avec ta methode habituelle.'
& (Join-Path $PSScriptRoot 'Launch-LocalFUT.ps1') -RemoteHost $RemoteHost -LSXMode ea-app -WaitForExternalGame `
    -GamePath $gamePath -UserConfigRoot (Join-Path $clientRoot 'config') -RuntimeDataRoot (Join-Path $clientRoot 'runtime')
