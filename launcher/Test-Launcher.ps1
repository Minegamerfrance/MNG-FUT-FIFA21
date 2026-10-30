$ErrorActionPreference='Stop'
$env:MNG_FUT_TEST_MODE='1'
$env:MNG_FUT_TEST_STATE=Join-Path $env:TEMP ('mng-launcher-test-'+[guid]::NewGuid().ToString('N'))
. (Join-Path $PSScriptRoot 'MNG-FUT.ps1')
function Assert($Condition,[string]$Message){if(-not $Condition){throw $Message}}
function Test-ManagedServerRunning {return [bool]$script:TestReady}
Assert ($AuthView.Visibility -eq 'Visible' -and $HomeView.Visibility -eq 'Collapsed') 'First launch must show authentication.'
Assert ($LaunchGameButton.Content -eq 'Choisir exe') 'Unconfigured game must show Choisir exe.'
Submit-Account
Assert ($LoginMessage.Text.Length -gt 0 -and -not $script:Profile) 'Empty form must not authenticate.'
Set-AuthMode 'register'
Assert ($LoginSubmitButton.Content -eq 'Créer mon compte') 'Registration mode must be explicit.'
Set-AuthMode 'login'
Assert ($LoginSubmitButton.Content -eq 'Se connecter') 'Login mode must be explicit.'
# Offline fake authentication: never create or modify a real account or club.
$LoginPasswordBox.Password='test-original';Set-PasswordVisible $true
Assert ($VisiblePasswordBox.Text -ceq 'test-original' -and $TogglePasswordButton.Content -eq 'Masquer') 'Reveal must display the entered password.'
$VisiblePasswordBox.Text='test-edited'
Assert ($LoginPasswordBox.Password -ceq 'test-edited') 'Visible edits must update the submitted password.'
Set-PasswordVisible $false
Assert ($VisiblePasswordBox.Text -eq '' -and $LoginPasswordBox.Password -ceq 'test-edited') 'Hiding must clear the preview and retain the password.'
Set-PasswordVisible $true;Set-AuthMode 'register'
Assert ($VisiblePasswordBox.Visibility -eq 'Collapsed') 'Switching authentication modes must hide the password.'
Set-AuthMode 'login'
function Try-AccountEndpoint($Mode,$Username,$Password){
 $script:AuthCalls++
 $script:Session=[pscustomobject]@{apiBaseUrl='https://test.invalid';token='test-only-token'}
 $script:Profile=[pscustomobject]@{id=999;username=$Username}
 Write-JsonFile $script:SessionPath $script:Session
 return @{ok=$true;message='OK'}
}
function Validate-Session {$script:Session=Read-JsonFile $script:SessionPath;$script:Profile=[pscustomobject]@{id=999;username='Test'};return $true}
$script:AuthCalls=0;Set-AuthMode 'register';$LoginUserBox.Text='jonas';$LoginPasswordBox.Password='1234567';Submit-Account
Assert ($script:AuthCalls -eq 0 -and $LoginMessage.Text -like '*8*128*') 'Registration must reject a short password before sending it.'
$LoginPasswordBox.Password=('a'*129);Submit-Account
Assert ($script:AuthCalls -eq 0 -and $LoginMessage.Text -like '*8*128*') 'Registration must explain an overly long password.'
$LoginUserBox.Text='j';$LoginPasswordBox.Password='test-only-password';Submit-Account
Assert ($script:AuthCalls -eq 0 -and $LoginMessage.Text -like '*3*24*') 'Registration must explain invalid usernames before submitting.'
Assert ($PasswordRulesText.Visibility -eq 'Visible') 'Registration must display the password rules.'
Set-AuthMode 'login'
$RememberCheckBox.IsChecked=$true;$LoginUserBox.Text='Test';$LoginPasswordBox.Password='test-only-password'
Submit-Account
Assert ($HomeView.Visibility -eq 'Visible' -and $AuthView.Visibility -eq 'Collapsed') 'Login must open FIFA 21 home.'
Assert ($LoginPasswordBox.Password -eq '') 'Password must be cleared after login.'
Assert ((Test-Path -LiteralPath $script:RememberPath) -and (Get-Settings).RememberMe) 'Remember option must persist.'
$protected=Get-Content -LiteralPath $script:RememberPath -Raw
Assert (-not $protected.Contains('test-only-token') -and -not $protected.Contains('test-only-password')) 'Remembered credentials must be encrypted and contain no password.'
$script:Session=$null;$script:Profile=$null
Assert (Restore-RememberedSession) 'Remembered session must restore.'
Assert ($script:Session.token -eq 'test-only-token') 'DPAPI round trip must preserve token.'
$RememberCheckBox.IsChecked=$false;Save-RememberedSession
Assert (-not(Test-Path -LiteralPath $script:RememberPath)) 'Unchecking remember must remove remembered credentials.'
Assert (-not(Restore-RememberedSession)) 'Unchecked remember must disable automatic sign-in.'
$fakeExe=Join-Path $script:StateRoot 'FIFA21.exe';[IO.File]::WriteAllText($fakeExe,'test fixture')
$settings=Get-Settings;Set-Property $settings 'Fifa21Exe' $fakeExe;Write-JsonFile $script:SettingsPath $settings;Apply-Language
Assert ($LaunchGameButton.Content -eq 'Lancer FIFA 21') 'Valid selection must become Lancer FIFA 21.'
Remove-Item -LiteralPath $fakeExe;Apply-Language
Assert ($LaunchGameButton.Content -eq 'Choisir exe') 'Missing executable must offer selection again.'
$script:Fifa21Starting=$true;Apply-Language
Assert (-not $LaunchGameButton.IsEnabled -and -not $LogoutButton.IsEnabled) 'Startup must prevent duplicate actions and account switching.'
$script:Fifa21Starting=$false;Apply-Language
$SettingsButton.RaiseEvent((New-Object Windows.RoutedEventArgs([Windows.Controls.Button]::ClickEvent)))
Assert ($SettingsDrawer.Visibility -eq 'Visible' -and $AppUpdateButton.IsEnabled) 'Settings must expose application updates.'
$SettingsDrawer.Visibility='Collapsed'
# Exercise the game launch path without starting FIFA, EA App or a connector.
[IO.File]::WriteAllText($fakeExe,'test fixture')
$testRoot=Join-Path $script:StateRoot 'connector';New-Item -ItemType Directory -Path $testRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../server/User-Settings.ps1') -Destination $testRoot
$env:LOCALFUT21_USER_CONFIG_ROOT=Join-Path $script:StateRoot 'user-settings'
New-Item -ItemType Directory -Path $env:LOCALFUT21_USER_CONFIG_ROOT | Out-Null
Write-JsonFile (Join-Path $env:LOCALFUT21_USER_CONFIG_ROOT 'launcher-settings.json') ([pscustomobject]@{eaAppLauncherPath=$fakeExe;eaAppOfferId='195853'})
function Start-Fifa21Server {$script:TestPrepared=$true}
function Test-ManagedServerRunning {return $script:TestReady}
function Get-Mng21Root {return $testRoot}
function Get-Process {return $null}
function Start-Process($FilePath,$ArgumentList){$script:TestLaunch=@($FilePath,$ArgumentList)}
$script:TestReady=$false;$script:TestLaunch=$null;Launch-SelectedGame
Assert (-not $script:TestLaunch) 'Game must not launch if server preparation failed.'
$script:TestReady=$true;Launch-SelectedGame
Assert ($script:TestPrepared -and $script:TestLaunch[1] -eq 'origin2://game/launch/?offerIds=195853&authCode=&cmdParams=') 'Game must launch through the configured EA App offer after server preparation.'
function Start-Fifa21Server {$script:TestReady=$true;$script:TestStarts++}
function Stop-SelectedServer {$script:TestReady=$false;$script:TestStops++}
$script:TestStarts=0;$script:TestStops=0;$script:TestReady=$false;Apply-Language
Assert ($PlayButton.Content -eq 'Lancer le serveur') 'Stopped server must offer start.'
$PlayButton.RaiseEvent((New-Object Windows.RoutedEventArgs([Windows.Controls.Button]::ClickEvent)))
Assert ($script:TestStarts -eq 1 -and $PlayButton.Content -eq 'Arrêter le serveur') 'Start click must switch to stop after confirmed startup.'
$PlayButton.RaiseEvent((New-Object Windows.RoutedEventArgs([Windows.Controls.Button]::ClickEvent)))
Assert ($script:TestStops -eq 1 -and $PlayButton.Content -eq 'Lancer le serveur') 'Stop click must stop the connector and switch back to start.'
$script:Fifa21Starting=$true;Apply-Language;Toggle-Server
Assert ($PlayButton.Content -eq 'Démarrage…' -and -not $PlayButton.IsEnabled -and $script:TestStarts -eq 1) 'Repeated clicks during startup must be ignored.'
$script:Fifa21Starting=$false;$script:Fifa21Stopping=$true;Apply-Language
Assert ($PlayButton.Content -eq 'Arrêt…' -and -not $PlayButton.IsEnabled) 'Stop in progress must disable the button.'
$script:Fifa21Stopping=$false;$script:TestReady=$true;Update-ServerButton
Assert ($PlayButton.Content -eq 'Arrêter le serveur') 'Refreshing must detect a pre-existing running connector.'
$script:TestReady=$false;Update-ServerButton
Assert ($PlayButton.Content -eq 'Lancer le serveur') 'Refreshing must detect an externally stopped connector.'
$script:TestReady=$true
function Stop-SelectedServer {throw 'test stop failure'}
Toggle-Server
Assert ($PlayButton.Content -eq 'Arrêter le serveur') 'A failed stop must retain the running state.'
$script:TestReady=$false
function Render-Preview([string]$Name){
 $content=$window.Content;$window.Content=$null
 if($content.Resources.MergedDictionaries.Count -eq 0){$content.Resources.MergedDictionaries.Add($window.Resources)}
 $content.Measure([Windows.Size]::new(1080,720));$content.Arrange([Windows.Rect]::new(0,0,1080,720));$content.UpdateLayout()
 $bitmap=New-Object Windows.Media.Imaging.RenderTargetBitmap(1080,720,96,96,[Windows.Media.PixelFormats]::Pbgra32)
 $bitmap.Render($content)
 $encoder=New-Object Windows.Media.Imaging.PngBitmapEncoder;$encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
 $file=[IO.File]::Create((Join-Path $script:StateRoot $Name));try{$encoder.Save($file)}finally{$file.Dispose()}
 $window.Content=$content
}
$script:Profile=$null;Update-AccountUi;Set-AuthMode 'login';$LoginUserBox.Clear();Set-OperationStatus 'Bienvenue sur MNG FUT';Render-Preview 'auth.png'
$script:Profile=[pscustomobject]@{id=999;username='Test'};Update-AccountUi;Render-Preview 'home.png'
$window.Close()
if($env:MNG_VERIFY_UPDATE_FEED -eq '1'){
 $manifest=Get-SignedManifest $script:LauncherManifestUrl
 Assert ($manifest.version -and $manifest.sha256 -match '^[a-fA-F0-9]{64}$' -and $manifest.size -gt 0) 'Signed update feed must contain a version and verified package metadata.'
 Write-Output ('PASS: live update feed signature verified, published version '+$manifest.version)
}
Write-Output ('PASS: authentication, remember session, DPAPI, executable selection, startup guards, settings. Previews: '+$script:StateRoot)
