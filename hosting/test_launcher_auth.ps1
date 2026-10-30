$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../launcher/Launcher-Core.ps1')
function Get-AuthBase {return 'https://test.invalid'}
function Invoke-JsonApi($Method,$Uri,$Body,$Headers,$TimeoutSec){
 $script:Calls.Add($Uri)
 $reply=$script:Replies.Dequeue()
 $errorObject=[Exception]::new('Remote request failed.')
 $errorObject|Add-Member -NotePropertyName Response -NotePropertyValue ([pscustomobject]@{StatusCode=$reply.Status})
 $record=[Management.Automation.ErrorRecord]::new($errorObject,'HttpFailure',[Management.Automation.ErrorCategory]::InvalidOperation,$null)
 $record.ErrorDetails=[Management.Automation.ErrorDetails]::new($reply.Body)
 throw $record
}
function Prepare($Replies){
 $script:Calls=New-Object 'Collections.Generic.List[string]'
 $script:Replies=New-Object Collections.Queue
 foreach($reply in $Replies){$script:Replies.Enqueue($reply)}
}
Prepare @(@{Status=400;Body='{"error":"INVALID_PASSWORD","message":"8-128 characters"}'})
$result=Try-AccountEndpoint 'register' 'jonas' '1234567'
if($result.ok -or $script:Calls.Count -ne 1 -or $result.message -notlike '*8*128*'){throw 'Password rejection was masked by a fallback request.'}
Prepare @(@{Status=409;Body='{"error":"USERNAME_TAKEN"}'})
$result=Try-AccountEndpoint 'register' 'existing' 'test-only-password'
if($script:Calls.Count -ne 1 -or $result.message -notlike '*utilis*'){throw 'Taken username error was lost.'}
Prepare @(@{Status=401;Body='{"error":"INVALID_CREDENTIALS"}'})
$result=Try-AccountEndpoint 'login' 'existing' 'test-only-password'
if($script:Calls.Count -ne 1 -or $result.message -notlike '*incorrect*'){throw 'Incorrect credentials were masked.'}
Prepare @(@{Status=404;Body='{}'},@{Status=400;Body='{"error":"INVALID_PASSWORD"}'})
$result=Try-AccountEndpoint 'register' 'legacy' '1234567'
if($script:Calls.Count -ne 2 -or $script:Calls[1] -notlike '*/api/auth/register' -or $result.message -notlike '*8*128*'){throw 'Legacy fallback must remain limited to missing routes.'}
Prepare @(@{Status=429;Body='{}'})
$result=Try-AccountEndpoint 'register' 'jonas' 'test-only-password'
if($script:Calls.Count -ne 1 -or $result.message -notlike '*tentatives*'){throw 'Rate limiting must not trigger retries.'}
Prepare @(@{Status=0;Body=''})
$result=Try-AccountEndpoint 'login' 'existing' 'test-only-password'
if($script:Calls.Count -ne 1 -or $result.message -notlike '*connexion*'){throw 'Network failure should be explained without duplicate submissions.'}
Write-Output 'PASS: registration and login preserve validation, conflict, authentication and rate-limit errors; fallback occurs only for missing routes.'
