$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot '../server/Launch-LocalFUT.ps1'
$tokens=$null;$errors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path $source),[ref]$tokens,[ref]$errors)
if($errors){throw ($errors.Message -join "`n")}
$definition=$tree.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Wait-ForServerPorts'},$true)
. ([scriptblock]::Create($definition.Extent.Text))
$script:Clock=[datetime]'2026-10-30T00:00:00Z'
$script:Start=$script:Clock
$script:ReadyAfter=20
$script:MissingPort=0
$script:PortChecks=0
$process=[pscustomobject]@{HasExited=$false}
function Get-Date {return $script:Clock}
function Start-Sleep($Milliseconds){$script:Clock=$script:Clock.AddMilliseconds($Milliseconds)}
function Get-Listener([int]$Port){
 $script:PortChecks++
 if(($script:Clock-$script:Start).TotalSeconds -ge $script:ReadyAfter -and $Port -ne $script:MissingPort){return [pscustomobject]@{LocalPort=$Port}}
}
if(Wait-ForServerPorts $process 15){throw 'Old deadline unexpectedly accepted a 20-second cold start.'}
$script:Clock=$script:Start
if(-not(Wait-ForServerPorts $process 75)){throw 'Cold authenticated club startup was rejected.'}
if(($script:Clock-$script:Start).TotalSeconds -gt 21){throw 'Ready connector waited for the full timeout.'}
$script:Clock=$script:Start;$script:ReadyAfter=0
if(-not(Wait-ForServerPorts $process 75) -or $script:Clock -ne $script:Start){throw 'Warm startup must complete immediately.'}
$script:MissingPort=10853
if(Wait-ForServerPorts $process 2){throw 'A partially started connector was accepted.'}
if(($script:Clock-$script:Start).TotalSeconds -gt 3){throw 'Missing port did not respect the deadline.'}
$process.HasExited=$true;$before=$script:PortChecks
if(Wait-ForServerPorts $process 75){throw 'Exited connector was accepted.'}
if($script:PortChecks -ne $before){throw 'Exited connector should fail immediately.'}
Write-Output 'PASS: cold start beyond 15 seconds, immediate warm start, required ports, bounded deadline and early process failure.'
