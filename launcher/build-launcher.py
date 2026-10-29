"""Assemble the self-contained WPF launcher; compile it with build-launcher.ps1."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
core = ROOT / 'Launcher-Core.ps1'

header = r'''$ErrorActionPreference='Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml, System.Windows.Forms, System.Net.Http, System.IO.Compression.FileSystem
$launcherPath=[string]$MyInvocation.MyCommand.Path
if(-not $launcherPath){$launcherPath=[Diagnostics.Process]::GetCurrentProcess().MainModule.FileName}
$script:AppRoot=Split-Path -Parent $launcherPath
if($env:MNG_FUT_LAUNCHER_ROOT){$script:AppRoot=$env:MNG_FUT_LAUNCHER_ROOT}
$script:StateRoot=Join-Path $env:LOCALAPPDATA 'MNGFUTLauncher'
if($env:MNG_FUT_TEST_MODE -eq '1' -and $env:MNG_FUT_TEST_STATE){$script:StateRoot=$env:MNG_FUT_TEST_STATE}
New-Item -ItemType Directory -Path $script:StateRoot -Force | Out-Null
$script:SettingsPath=Join-Path $script:StateRoot 'launcher-oneclick.json'
$script:SessionPath=Join-Path $script:StateRoot 'mng-cloud-session.json'
$script:Session=$null;$script:Profile=$null
$script:SelectedGame='21';$script:Lang='fr';$script:LauncherVersion='1.3.29'
$script:AuthApiDefault='https://mng-fut-api.minegamerfrance.workers.dev'
$script:LauncherManifestUrl='https://raw.githubusercontent.com/Minegamerfrance/MinegamerServeur17/main/updates/launcher-manifest.json'
$script:GameServerManifestUrl='https://raw.githubusercontent.com/Minegamerfrance/MinegamerServeur17/main/updates/game-servers-manifest.json'
function Get-Settings {
 $settings=Read-JsonFile $script:SettingsPath
 if(-not $settings){$settings=[pscustomobject]@{}}
 foreach($entry in @(@{Name='Fifa21Exe';Value=''},@{Name='Fifa21ServerRoot';Value=(Join-Path $script:AppRoot 'fifa21-server')},@{Name='RememberMe';Value=$false},@{Name='CloudApiBaseUrl';Value=$script:AuthApiDefault})){
  if($settings.PSObject.Properties.Name -notcontains $entry.Name){Set-Property $settings $entry.Name $entry.Value}
 }
 return $settings
}
'''
integration = (ROOT / 'MNG-FIFA21.ps1').read_text(encoding='utf-8-sig')
integration = integration[:integration.index("if (Get-Command C -CommandType Function")]
(ROOT / 'MNG-FUT.ps1').write_text(header + '\n' + core.read_text(encoding='utf-8-sig') + '\n' + integration + '\n' + (ROOT / 'FIFA21-Interface.ps1').read_text(encoding='utf-8-sig'), encoding='utf-8-sig', newline='\n')
print('Assembled MNG FUT 1.3.29')
