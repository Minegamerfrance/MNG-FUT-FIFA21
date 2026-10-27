param([switch]$OriginalClub)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"{0}"' -f $PSCommandPath))
    if($OriginalClub){$arguments+='-OriginalClub'}
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -WindowStyle Hidden -Wait
    exit
}

try {
    $normalConfig=Join-Path $env:LOCALAPPDATA 'MNG21\LocalFUT'
    $launcher=Join-Path $env:LOCALAPPDATA 'MNGFUTLauncher\launcher-oneclick.json'
    $game=''
    if(Test-Path -LiteralPath $launcher){$settings=Get-Content -LiteralPath $launcher -Raw -Encoding UTF8|ConvertFrom-Json;$game=[string]$settings.Fifa21Exe}
    if(-not $game -and (Test-Path -LiteralPath (Join-Path $normalConfig 'launcher-settings.json'))){$settings=Get-Content -LiteralPath (Join-Path $normalConfig 'launcher-settings.json') -Raw -Encoding UTF8|ConvertFrom-Json;$game=[string]$settings.gamePath}
    if(-not $game -or -not(Test-Path -LiteralPath $game)){
        Add-Type -AssemblyName System.Windows.Forms
        $picker=New-Object Windows.Forms.OpenFileDialog;$picker.Filter='FIFA 21|FIFA21.exe';$picker.Title='Choisis FIFA21.exe'
        if($picker.ShowDialog() -ne 'OK'){return};$game=$picker.FileName
    }
    & (Join-Path $PSScriptRoot 'Stop-LocalFUT.ps1')
    if($OriginalClub){
        $env:LOCALFUT_RUNTIME_ROOT=Join-Path $env:LOCALAPPDATA 'FIFA21LocalFUT'
        $config=$normalConfig
    }else{
        $profile=Join-Path $env:LOCALAPPDATA 'MNG21\profiles\debut-test'
        $env:LOCALFUT_RUNTIME_ROOT=Join-Path $profile 'runtime'
        $config=Join-Path $profile 'config'
    }
    $env:LOCALFUT21_USER_CONFIG_ROOT=$config
    & (Join-Path $PSScriptRoot 'Launch-LocalFUT.ps1') -GamePath $game -UserConfigRoot $config -RuntimeDataRoot $env:LOCALFUT_RUNTIME_ROOT -WaitForExternalGame
}catch{
    Add-Type -AssemblyName PresentationFramework
    [Windows.MessageBox]::Show($_.Exception.Message,'MNG FUT 21')|Out-Null
}
