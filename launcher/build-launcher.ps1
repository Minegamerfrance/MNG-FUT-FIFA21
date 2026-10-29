param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
& C:\Python314\python.exe (Join-Path $PSScriptRoot 'build-launcher.py')
if($LASTEXITCODE -ne 0){throw 'Launcher assembly failed.'}
$source=Join-Path $PSScriptRoot 'MNG-FUT.ps1'
$tokens=$null;$parseErrors=$null
$null=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors){throw ($parseErrors.Message -join "`n")}
Import-Module 'C:\Users\Mineg\Documents\PowerShell\Modules\ps2exe\1.0.18\ps2exe.psd1'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
Invoke-ps2exe -inputFile $source -outputFile (Join-Path $OutputDirectory 'MNG FUT.exe') -noConsole -requireAdmin -STA -DPIAware -title 'MNG FUT — FIFA 21' -product 'MNG FUT' -version '1.3.30.0' -company 'MNG FUT' -iconFile 'C:\Users\Mineg\Desktop\serveur fifa 17\MNG-FUT.ico'
