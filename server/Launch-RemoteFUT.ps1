[CmdletBinding()]
param([string]$RemoteHost='')
$ErrorActionPreference = 'Stop'
if (-not $RemoteHost) { $RemoteHost = Read-Host 'Adresse Tailscale du PC serveur (100.x.x.x)' }
if ($RemoteHost -notmatch '^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$') { throw 'Adresse Tailscale IPv4 attendue.' }
Write-Host 'Mode serveur distant prive : aucun club ne sera heberge sur ce connecteur.'
Write-Host 'Ferme le serveur FUT local avant de continuer, puis lance FIFA avec ta methode habituelle.'
& (Join-Path $PSScriptRoot 'Launch-LocalFUT.ps1') -RemoteHost $RemoteHost -LSXMode ea-app -WaitForExternalGame
