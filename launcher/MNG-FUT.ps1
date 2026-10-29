$ErrorActionPreference='Stop'
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

function Read-JsonFile([string]$Path){

    if(-not(Test-Path -LiteralPath $Path)){ return $null }

    try { return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }

    catch { return $null }

}

function Write-JsonFile([string]$Path,$Object){

    $dir=Split-Path -Parent $Path

    if($dir){New-Item -ItemType Directory -Force -Path $dir | Out-Null}

    $json=$Object | ConvertTo-Json -Depth 12

    [IO.File]::WriteAllText($Path,$json,(New-Object Text.UTF8Encoding($false)))

}

function Set-Property($obj,[string]$name,$value){

    if($obj.PSObject.Properties.Name -contains $name){ $obj.$name=$value }

    else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value }

}

function T([string]$en,[string]$fr,[string]$es){

    if($script:Lang -eq 'fr'){return $fr}

    if($script:Lang -eq 'es'){return $es}

    return $en

}

function Get-HexBytes([string]$hex){[byte[]]$bytes=New-Object byte[] ($hex.Length/2);for($i=0;$i -lt $bytes.Length;$i++){$bytes[$i]=[Convert]::ToByte($hex.Substring($i*2,2),16)};Write-Output -NoEnumerate $bytes}

function Get-SignedManifest([string]$url){

    $lastError='Manifest signature is invalid.'

    for($attempt=1;$attempt -le 4;$attempt++){

        $client=$null;$key=$null;$ecdsa=$null;$sha=$null

        try{

            $nonce=[DateTime]::UtcNow.Ticks;$separator=if($url.Contains('?')){'&'}else{'?'};$manifestUrl=$url+$separator+'mng='+$nonce;$signatureUrl=$url+'.sig'+$separator+'mng='+$nonce

            $client=New-Object Net.Http.HttpClient;$client.DefaultRequestHeaders.CacheControl=New-Object Net.Http.Headers.CacheControlHeaderValue;$client.DefaultRequestHeaders.CacheControl.NoCache=$true;$client.DefaultRequestHeaders.CacheControl.NoStore=$true

            if($url -in @($script:LauncherManifestUrl,$script:GameServerManifestUrl)){

                $client.DefaultRequestHeaders.UserAgent.ParseAdd('MNG-FUT-Launcher');$apiRoot='https://api.github.com/repos/Minegamerfrance/MinegamerServeur17/';$revision=$client.GetStringAsync($apiRoot+'commits/main?mng='+$nonce).GetAwaiter().GetResult()|ConvertFrom-Json

                if([string]$revision.sha -notmatch '^[a-f0-9]{40}$'){throw 'Invalid publication revision.'}

                $manifestName=[IO.Path]::GetFileName(([Uri]$url).AbsolutePath);$manifestApi=$apiRoot+'contents/updates/'+$manifestName+'?ref='+$revision.sha+'&mng='+$nonce;$signatureApi=$apiRoot+'contents/updates/'+$manifestName+'.sig?ref='+$revision.sha+'&mng='+$nonce

                $manifestPayload=$client.GetStringAsync($manifestApi).GetAwaiter().GetResult()|ConvertFrom-Json;$signaturePayload=$client.GetStringAsync($signatureApi).GetAwaiter().GetResult()|ConvertFrom-Json

                $data=[Convert]::FromBase64String(([string]$manifestPayload.content -replace '\s',''));$signatureText=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(([string]$signaturePayload.content -replace '\s','')));$signature=[Convert]::FromBase64String($signatureText.Trim())

            }else{$data=$client.GetByteArrayAsync($manifestUrl).GetAwaiter().GetResult();$signature=[Convert]::FromBase64String(($client.GetStringAsync($signatureUrl).GetAwaiter().GetResult()).Trim())}

            $x=Get-HexBytes '10f99d18b877af169c4012024f48a7bd909436112476b44df7758ff88fe47a92';$y=Get-HexBytes '8c7b9013a62228ce93b65e36878d7d6f78b87e1efd2d72a51dca35c276483b5e';$blob=New-Object byte[] 72

            [Buffer]::BlockCopy([BitConverter]::GetBytes(0x31534345),0,$blob,0,4);[Buffer]::BlockCopy([BitConverter]::GetBytes(32),0,$blob,4,4);[Buffer]::BlockCopy($x,0,$blob,8,32);[Buffer]::BlockCopy($y,0,$blob,40,32)

            $key=[Security.Cryptography.CngKey]::Import($blob,[Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob);$ecdsa=New-Object Security.Cryptography.ECDsaCng($key);$sha=[Security.Cryptography.SHA256]::Create()

            if($ecdsa.VerifyHash($sha.ComputeHash($data),$signature)){return ([Text.Encoding]::UTF8.GetString($data)|ConvertFrom-Json)}

            $lastError='Manifest signature is invalid.'

        }catch{$lastError=$_.Exception.Message

        }finally{if($sha){$sha.Dispose()};if($ecdsa){$ecdsa.Dispose()};if($key){$key.Dispose()};if($client){$client.Dispose()}}

        if($attempt -lt 4){Start-Sleep -Milliseconds 500}

    }

    throw $lastError

}

function Resolve-ManifestUrl([string]$manifestUrl,[string]$source){$absolute=$null;if([Uri]::TryCreate($source,[UriKind]::Absolute,[ref]$absolute)){return $absolute.AbsoluteUri};return ([Uri]::new([Uri]$manifestUrl,$source)).AbsoluteUri}

function Save-VerifiedDownload([string]$url,[string]$path,[string]$sha256,[long]$size){

    $dir=Split-Path -Parent $path;if($dir){New-Item -ItemType Directory -Path $dir -Force|Out-Null};(New-Object Net.WebClient).DownloadFile($url,$path);$item=Get-Item -LiteralPath $path

    if($size -gt 0 -and $item.Length -ne $size){throw 'Downloaded file size is invalid.'};$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();if($sha256 -and $hash -ne $sha256.ToLowerInvariant()){throw 'Downloaded file SHA256 is invalid.'}

}

function Expand-MngZip([string]$Path,[string]$Destination){

    if(-not(Test-Path -LiteralPath $Path)){throw 'ZIP package is missing.'}

    New-Item -ItemType Directory -Path $Destination -Force|Out-Null

    [IO.Compression.ZipFile]::ExtractToDirectory([IO.Path]::GetFullPath($Path),[IO.Path]::GetFullPath($Destination))

}

function Wait-Ui([int]$Milliseconds){

    $until=[DateTime]::UtcNow.AddMilliseconds($Milliseconds)

    do{

        Start-Sleep -Milliseconds 25

        if($window){$window.Dispatcher.Invoke([action]{},[Windows.Threading.DispatcherPriority]::Background)}

    }while([DateTime]::UtcNow -lt $until)

}

function Set-OperationStatus([string]$text,[string]$color='#E3CF66'){$LaunchStatus.Text='●  '+$text;$LaunchStatus.Foreground=$color;$window.Dispatcher.Invoke([action]{},[Windows.Threading.DispatcherPriority]::Background)}

function Update-ApplicationInternal(){

    try{

        Set-OperationStatus (T 'Checking application update...' 'Recherche de mise à jour application...' 'Buscando actualización de la aplicación...');$manifest=Get-SignedManifest $script:LauncherManifestUrl

        if([version]$manifest.version -le [version]$script:LauncherVersion){Set-OperationStatus (T 'Application is up to date' 'Application à jour' 'Aplicación actualizada') '#87DB72';[Windows.MessageBox]::Show((T 'MNG FUT is up to date.' 'MNG FUT est à jour.' 'MNG FUT está actualizado.'),'MNG FUT')|Out-Null;return}

        $answer=[Windows.MessageBox]::Show(((T 'Install MNG FUT update ' 'Installer la mise à jour MNG FUT ' 'Instalar actualización MNG FUT ')+$manifest.version+' ?'),'MNG FUT',[Windows.MessageBoxButton]::YesNo,[Windows.MessageBoxImage]::Question);if($answer -ne [Windows.MessageBoxResult]::Yes){return}

        Set-OperationStatus (T 'Downloading application update...' 'Téléchargement de la mise à jour...' 'Descargando actualización...');$updateRoot=Join-Path $env:TEMP ('MNGFUT-V1-Update-'+[guid]::NewGuid().ToString('N'));$zip=Join-Path $updateRoot 'update.zip';$payload=Join-Path $updateRoot 'payload';New-Item -ItemType Directory -Path $payload -Force|Out-Null

        Save-VerifiedDownload (Resolve-ManifestUrl $script:LauncherManifestUrl ([string]$manifest.source)) $zip ([string]$manifest.sha256) ([long]$manifest.size);Expand-MngZip $zip $payload

        $newExe=Get-ChildItem -LiteralPath $payload -Filter 'MNG FUT.exe' -File -Recurse|Select-Object -First 1;if(-not $newExe){throw 'MNG FUT.exe is missing from update package.'};$packageRoot=$newExe.Directory.FullName;$updater=Join-Path $updateRoot 'apply-update.ps1'

        $source64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($packageRoot));$target64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script:AppRoot));$updateLog64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Join-Path $script:StateRoot 'launcher-update.log')));$launcherPid=$PID

        $updateCode=@"

`$ErrorActionPreference='Stop'

`$source=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$source64'))

`$target=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$target64'))

`$log=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$updateLog64'))

try {

    if([string]::IsNullOrWhiteSpace(`$source) -or [string]::IsNullOrWhiteSpace(`$target)){throw 'Update source or destination is empty.'}

    Wait-Process -Id $launcherPid -Timeout 60 -ErrorAction SilentlyContinue

    Start-Sleep -Milliseconds 800

    New-Item -ItemType Directory -Path `$target -Force|Out-Null

    Get-ChildItem -LiteralPath `$source -Force|ForEach-Object { Copy-Item -LiteralPath `$_.FullName -Destination `$target -Recurse -Force }

    `$launcher=Join-Path `$target 'MNG FUT.exe'

    if(-not(Test-Path -LiteralPath `$launcher)){throw 'Updated launcher executable is missing.'}

    Start-Process -FilePath `$launcher -WorkingDirectory `$target

} catch {

    ('['+(Get-Date -Format s)+'] '+`$_.Exception.ToString())|Out-File -LiteralPath `$log -Encoding UTF8 -Append

}

"@

        [IO.File]::WriteAllText($updater,$updateCode,(New-Object Text.UTF8Encoding($false)));$arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$updater+'"';Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden|Out-Null;$window.Close()

    }catch{Set-OperationStatus (T 'Application update failed' 'Échec de la mise à jour' 'Error de actualización') '#E76F6F';[Windows.MessageBox]::Show($_.Exception.Message,'MNG FUT')|Out-Null}

}

function Get-AuthBase(){

    $settings=Get-Settings

    $base=[string]$settings.CloudApiBaseUrl

    if([string]::IsNullOrWhiteSpace($base)){ $base=$script:AuthApiDefault }

    return $base.TrimEnd('/')

}

function Get-SessionToken(){

    if($script:Session -and $script:Session.token){ return [string]$script:Session.token }

    return ''

}

function Invoke-JsonApi([string]$Method,[string]$Uri,$Body=$null,[hashtable]$Headers=$null,[int]$TimeoutSec=12){

    $params=@{Method=$Method;Uri=$Uri;TimeoutSec=$TimeoutSec;UseBasicParsing=$true;ErrorAction='Stop'}

    if($Headers){$params.Headers=$Headers}

    if($null -ne $Body){

        $params.ContentType='application/json; charset=utf-8'

        $params.Body=($Body|ConvertTo-Json -Depth 10 -Compress)

    }

    return Invoke-RestMethod @params

}

function Validate-Session(){

    $script:Session=Read-JsonFile $script:SessionPath

    if(-not $script:Session -or -not $script:Session.token){$script:Profile=$null;return $false}

    $base=[string]$script:Session.apiBaseUrl

    if([string]::IsNullOrWhiteSpace($base)){$base=Get-AuthBase}

    try{

        $r=Invoke-JsonApi 'GET' ($base.TrimEnd('/')+'/api/me') $null @{Authorization=('Bearer '+[string]$script:Session.token);Accept='application/json'} 8

        if($r -and $r.ok -eq $true -and $r.profile){

            $script:Profile=$r.profile

            Set-Property $script:Session 'profile' $r.profile

            Set-Property $script:Session 'apiBaseUrl' $base.TrimEnd('/')

            Set-Property $script:Session 'savedAt' ([DateTime]::UtcNow.ToString('o'))

            Write-JsonFile $script:SessionPath $script:Session

            return $true

        }

    }catch{}

    $script:Profile=$null

    return $false

}

function Try-AccountEndpoint([string]$Mode,[string]$Username,[string]$Password){

    $base=Get-AuthBase

    $paths = if($Mode -eq 'register'){@('/api/register','/api/auth/register')}else{@('/api/login','/api/auth/login')}

    $last='Connexion refusee.'

    foreach($path in $paths){

        try{

            $r=Invoke-JsonApi 'POST' ($base+$path) @{username=$Username;password=$Password} $null 12

            $token=''

            if($r.token){$token=[string]$r.token}

            elseif($r.accessToken){$token=[string]$r.accessToken}

            elseif($r.session -and $r.session.token){$token=[string]$r.session.token}

            if($token){

                $accountProfile=$r.profile

                $session=[pscustomobject]@{apiBaseUrl=$base;token=$token;profile=$accountProfile;savedAt=[DateTime]::UtcNow.ToString('o')}

                Write-JsonFile $script:SessionPath $session

                $script:Session=$session

                if(Validate-Session){return @{ok=$true;message='OK'}}

                Remove-Item -LiteralPath $script:SessionPath -Force -ErrorAction SilentlyContinue

                $last='Le serveur a renvoye un token invalide.'

            } else { $last='Reponse de connexion sans token.' }

        }catch{

            $last=$_.Exception.Message

        }

    }

    return @{ok=$false;message=$last}

}

function Read-ServerLogFile([string]$Path,[int]$MaxCharacters=18000){

    if(-not(Test-Path -LiteralPath $Path)){return ''}

    try{

        $stream=New-Object IO.FileStream($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)

        try{$reader=New-Object IO.StreamReader($stream);$text=$reader.ReadToEnd();$reader.Dispose()}finally{$stream.Dispose()}

        if($text.Length -gt $MaxCharacters){return $text.Substring($text.Length-$MaxCharacters)}

        return $text

    }catch{return ''}

}


function Update-Mng21Package([switch]$CheckOnly,[switch]$Force) {
    $settings=Get-Settings
    $root=if($settings.Fifa21ServerRoot){[string]$settings.Fifa21ServerRoot}else{Join-Path $script:AppRoot 'fifa21-server'}
    if(-not [IO.Path]::IsPathRooted($root)){$root=Join-Path $script:AppRoot $root}
    $packagedRoot = Join-Path $script:AppRoot 'fifa21-server'
    if (Test-Path -LiteralPath (Join-Path $packagedRoot 'account-server.json')) { $root = $packagedRoot }
    if (Test-Path -LiteralPath (Join-Path $root 'account-server.json')) {
        Set-OperationStatus 'FIFA 21 utilise le serveur en ligne MNG. Le catalogue est gere sur le serveur.' '#87DB72'
        return
    }
    $updater=Join-Path $script:AppRoot 'FIFA21-Update.py'
    if(-not(Test-Path -LiteralPath $updater)){throw 'Le programme de mise à jour FIFA 21 est manquant.'}
    $python=Get-Command python.exe -ErrorAction SilentlyContinue
    $pythonArgs=@()
    if(-not $python){$python=Get-Command py.exe -ErrorAction SilentlyContinue;$pythonArgs=@('-3')}
    if(-not $python){throw 'Installe Python 3 pour utiliser le serveur FIFA 21.'}
    Set-OperationStatus 'Vérification du serveur FIFA 21 sur GitHub…'
    $output=& $python.Source @pythonArgs $updater --target $root --check 2>&1
    if($LASTEXITCODE -ne 0){throw ($output -join "`n")}
    $result=($output -join "`n")|ConvertFrom-Json
    if($CheckOnly -and -not $result.updateAvailable){Set-OperationStatus ('FIFA 21 est à jour : '+$result.version) '#87DB72';return}
    if(-not $Force -and -not $result.updateAvailable){Set-OperationStatus ('FIFA 21 est à jour : '+$result.version) '#87DB72';return}
    if((Test-Path -LiteralPath (Join-Path $root 'runtime-source\localfut21\server.py')) -and (Test-ManagedServerRunning '21')){Stop-SelectedServer}
    Set-OperationStatus 'Installation de FIFA 21 depuis son dépôt GitHub…'
    $argsList=@('--target',$root);if($Force){$argsList+='--force'}
    $output=& $python.Source @pythonArgs $updater @argsList 2>&1
    if($LASTEXITCODE -ne 0){throw ($output -join "`n")}
    Set-Property $settings 'Fifa21ServerRoot' $root
    Write-JsonFile $script:SettingsPath $settings
    Set-OperationStatus ('Serveur FIFA 21 installé : '+$result.version) '#87DB72'
}
# Embedded in MNG FUT by Build-Integration.ps1. MNG FUT owns its runtime and club.
$script:Fifa21Starting = $false
$script:Fifa21Stopping = $false
function Start-Mng21BackgroundWorker([string]$Arguments,[string]$Root) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $info.Arguments = '-WindowStyle Hidden '+$Arguments
    $info.WorkingDirectory = $Root
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    return [Diagnostics.Process]::Start($info)
}
function Get-Mng21Root {
    $configuration = Get-Settings
    $root = if ($configuration.Fifa21ServerRoot) { [string]$configuration.Fifa21ServerRoot } else { Join-Path $script:AppRoot 'fifa21-server' }
    if (-not [IO.Path]::IsPathRooted($root)) { $root = Join-Path $script:AppRoot $root }
    $root = [IO.Path]::GetFullPath($root)
    $packagedRoot = Join-Path $script:AppRoot 'fifa21-server'
    if (Test-Path -LiteralPath (Join-Path $packagedRoot 'account-server.json')) { $root = $packagedRoot }
    $accountMode = Test-Path -LiteralPath (Join-Path $root 'account-server.json')
    if (-not $accountMode -and -not (Test-Path -LiteralPath (Join-Path $root 'runtime-source\localfut21\server.py'))) { Update-Mng21Package }
    $required = if ($accountMode) { @('Launch-LocalFUT.ps1','Stop-LocalFUT.ps1','User-Settings.ps1','runtime-source\account_client.py','runtime-source\account_transport.py','remote-runtime.json') } else { @('Launch-LocalFUT.ps1','Stop-LocalFUT.ps1','User-Settings.ps1','runtime-source\localfut21\server.py') }
    foreach ($file in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $file) -PathType Leaf)) { throw "Les fichiers MNG FUT FIFA 21 sont incomplets : $root ($file)." }
    }
    return $root
}
function Test-Mng21Owner($ProcessInfo, [string]$ScriptPath) {
    if (-not $ProcessInfo -or -not $ProcessInfo.CommandLine) { return $false }
    $command = ([string]$ProcessInfo.CommandLine).Replace('/','\')
    $expected = [IO.Path]::GetFullPath($ScriptPath)
    return $command -match ('(?i)(?:^|[\s"])' + [regex]::Escape($expected) + '(?:[\s"]|$)')
}
function Test-ManagedServerRunning([string]$GameId=$script:SelectedGame) {
    if ($GameId -ne '21') { return Test-LegacyManagedServerRunning $GameId }
    try {
        $root = Get-Mng21Root
        $needsProfile = $false
        $accountMode = Test-Path -LiteralPath (Join-Path $root 'account-server.json')
        $backendScript = if ($accountMode) { 'account_client.py' } else { 'localfut21\server.py' }
        if ($accountMode) {
            $connectionStatus = Read-JsonFile (Join-Path $root 'runtime\status.json')
            if (-not $script:Profile -or [long]$connectionStatus.accountId -ne [long]$script:Profile.id) { return $false }
        }
        foreach ($entry in @(@{Port=8090;Script=$backendScript},@{Port=44321;Script=$backendScript},@{Port=42230;Script='redirector_tls.py'})) {
            $listener = Get-NetTCPConnection -State Listen -LocalPort $entry.Port -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -in @('127.0.0.1','0.0.0.0','::','::1') } | Select-Object -First 1
            if (-not $listener) { return $false }
            $owner = try { Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess) -ErrorAction Stop } catch { $null }
            if ($owner -and $owner.CommandLine) {
                if (-not (Test-Mng21Owner $owner (Join-Path $root ('runtime-source\'+$entry.Script)))) { return $false }
            } else {
                # A normal launcher cannot inspect an elevated Python command line.
                # Verify the live server's source fingerprint instead of reporting failure.
                $needsProfile = $true
            }
        }
        if ($needsProfile) {
            $profile = Invoke-RestMethod -Uri 'http://127.0.0.1:8090/localfut/auth/bootstrap' -TimeoutSec 2 -MaximumRedirection 0 -ErrorAction Stop
            if ($profile.version -ne 1) { return $false }
            foreach ($pair in @(@('serverSourceSha256','server.py'),@('onboardingSourceSha256','onboarding.py'))) {
                if ($accountMode) {
                    $contract = Read-JsonFile (Join-Path $root 'remote-runtime.json')
                    $hash = if ($pair[1] -eq 'server.py') { [string]$contract.server } else { [string]$contract.onboarding }
                } else { $hash = (Get-FileHash -LiteralPath (Join-Path $root ('runtime-source\localfut21\'+$pair[1])) -Algorithm SHA256).Hash }
                if ([string]$profile.($pair[0]) -ine $hash) { return $false }
            }
        }
        return $true
    } catch { return $false }
}
function Apply-Language {
    Apply-LegacyLanguage
    if ($StopFifa21Button) { $StopFifa21Button.Visibility = if ($script:SelectedGame -eq '21') { 'Visible' } else { 'Collapsed' } }
    if ($script:SelectedGame -ne '21') { return }
    $running = Test-ManagedServerRunning '21'
    $configuration = Get-Settings
    $displayRoot = if ($configuration.Fifa21ServerRoot) { [string]$configuration.Fifa21ServerRoot } else { Join-Path $script:AppRoot 'fifa21-server' }
    if (-not [IO.Path]::IsPathRooted($displayRoot)) { $displayRoot = Join-Path $script:AppRoot $displayRoot }
    $packagedRoot = Join-Path $script:AppRoot 'fifa21-server'
    if (Test-Path -LiteralPath (Join-Path $packagedRoot 'account-server.json')) { $displayRoot = $packagedRoot }
    $accountMode = Test-Path -LiteralPath (Join-Path $displayRoot 'account-server.json')
    $PlayButton.Content = T '▶   START SERVER' '▶   DÉMARRER LE SERVEUR' '▶   INICIAR SERVIDOR'
    if ($accountMode) { $PlayButton.Content = T '▶   CONNECT TO FUT' '▶   SE CONNECTER À FUT' '▶   CONECTARSE A FUT' }
    if ($StopFifa21Button) {
        $StopFifa21Button.Content = T '■   STOP SERVER' '■   ARRÊTER LE SERVEUR' '■   DETENER SERVIDOR'
        if ($accountMode) { $StopFifa21Button.Content = T '■   DISCONNECT' '■   SE DÉCONNECTER' '■   DESCONECTARSE' }
        $StopFifa21Button.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    }
    if ($GameHeaderText) { $GameHeaderText.Text = if ($script:Fifa21Starting) { 'FIFA 21 • PRÉPARATION EN COURS' } elseif ($running) { 'FIFA 21 • SERVEUR DÉMARRÉ' } else { 'FIFA 21 • SERVEUR ARRÊTÉ' } }
    if ($accountMode -and $GameHeaderText) { $GameHeaderText.Text = if ($script:Fifa21Starting) { 'FIFA 21 • CONNEXION EN COURS' } elseif ($running) { 'FIFA 21 • CLUB PERSONNEL CONNECTÉ' } else { 'FIFA 21 • SERVEUR EN LIGNE' } }
    $LaunchGameButton.Content = '▶   LANCER FIFA'
    $PlayButton.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    $LaunchGameButton.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    $SettingsHint.Text = 'Le serveur reste actif. Lance FIFA manuellement ; les nouvelles sessions sont détectées automatiquement.'
    if ($accountMode) { $SettingsHint.Text = 'Créez un compte ou connectez-vous à MNG FUT pour retrouver votre club personnel sur le serveur en ligne.' }
}
function Refresh-ServerLogs {
    if ($script:SelectedGame -ne '21') { Refresh-LegacyServerLogs; return }
    try {
        $root = Get-Mng21Root
        $sections = @()
        foreach ($name in @('status.json','mng-launch.log','mng-stop.log','server.log','server.error.log','redirector.log','redirector.error.log','trust-patch.log','auth-bridge.log','ea-app-launch.log')) {
            $content = Read-ServerLogFile (Join-Path $root ('runtime\'+$name))
            if ($content) { $sections += ('[FIFA 21 - '+$name+"]`r`n"+$content) }
        }
        $text = $sections -join "`r`n`r`n"
        if ($ServerLogsBox.Text -ne $text) { $ServerLogsBox.Text = $text; $ServerLogsBox.ScrollToEnd() }
    } catch { $ServerLogsBox.Text = $_.Exception.Message }
}
function Test-Mng21GamePrepared($Games, $Status, [string]$Exe) {
    if (-not $Games -or -not $Status -or $Status.connection -notlike 'LOCAL ROUTING ARMED*') { return $false }
    if ([string]$Status.game -notmatch '^RUNNING \(PID (\d+);') { return $false }
    $preparedGameId = [int]$Matches[1]
    foreach ($game in $Games) {
        if ($game.Id -eq $preparedGameId -and $game.Path -and [IO.Path]::GetFullPath($game.Path) -ieq [IO.Path]::GetFullPath($Exe)) { return $true }
    }
    return $false
}
function Start-Fifa21Server([switch]$LaunchGame) {
    if ($script:Fifa21Starting) { return }
    $script:Fifa21Starting = $true
    try {
        $root = Get-Mng21Root
        $accountConfig = Join-Path $root 'account-server.json'
        $accountMode = Test-Path -LiteralPath $accountConfig
        if ($accountMode -and -not (Validate-Session)) {
            Open-Account
            throw 'Connecte-toi ou cree ton compte MNG pour acceder a ton club FIFA 21.'
        }
        if ($accountMode) {
            $clientPython = Join-Path $root '.venv\Scripts\python.exe'
            $prepared = $false
            if (Test-Path -LiteralPath $clientPython) {
                & $clientPython -c 'import cryptography' 2>$null
                $prepared = $LASTEXITCODE -eq 0
            }
            if (-not $prepared) {
                Set-OperationStatus 'Preparation de votre premiere connexion MNG FUT…'
                $prepare = Start-Mng21BackgroundWorker ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -AccountMode' -f (Join-Path $root 'Prepare-RemoteClient.ps1')) $root
                while (-not $prepare.HasExited) { Wait-Ui 300 }
                if ($prepare.ExitCode -ne 0) { throw 'La preparation du connecteur a echoue. Verifie que Python est installe.' }
            }
        }
        $exe = Get-SelectedGameExe
        if (-not $exe -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { Choose-GameExe; $exe = Get-SelectedGameExe }
        if (-not $exe -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { return }
        $games = @(Get-Process -Name FIFA21 -ErrorAction SilentlyContinue)
        $currentStatus = Read-JsonFile (Join-Path $root 'runtime\status.json')
        $tracked = Read-JsonFile (Join-Path $root 'runtime\launcher-processes.json')
        $waiter = if ($tracked.externalWaitPid) { Get-Process -Id ([int]$tracked.externalWaitPid) -ErrorAction SilentlyContinue } else { $null }
        if ((Test-ManagedServerRunning '21') -and ((Test-Mng21GamePrepared $games $currentStatus $exe) -or (-not $games -and $waiter -and $currentStatus.connection -like 'WAITING EXTERNAL GAME*'))) {
            Set-OperationStatus 'Serveur démarré. Lance FIFA 21 avec ton lanceur habituel.' '#87DB72'; return
        }
        # Let MNG FUT verify/reuse its own listeners. Never kill a port owner here.
        $log = Join-Path $root 'runtime\mng-launch.log'
        $configRoot = if ($env:LOCALFUT21_USER_CONFIG_ROOT) { $env:LOCALFUT21_USER_CONFIG_ROOT } else { Join-Path $env:LOCALAPPDATA 'MNG21\LocalFUT' }
        $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -GamePath "{1}" -UserConfigRoot "{2}" -LauncherLogPath "{3}"' -f (Join-Path $root 'Launch-LocalFUT.ps1'),$exe,$configRoot,$log
        $arguments += ' -WaitForExternalGame'
        if ($accountMode) {
            $arguments += ' -AccountGatewayConfig "{0}" -AccountSessionPath "{1}" -LSXMode ea-app' -f $accountConfig,$script:SessionPath
        }
        if ($games) {
            foreach ($game in $games) {
                if (-not $game.Path -or [IO.Path]::GetFullPath($game.Path) -ine [IO.Path]::GetFullPath($exe)) { throw 'Le FIFA 21 ouvert ne correspond pas au chemin choisi dans MNG FUT.' }
            }
        }
        Apply-Language
        Set-OperationStatus 'Démarrage du serveur MNG FUT…'
        $worker = Start-Mng21BackgroundWorker $arguments $root
        $null = $worker.Handle
        # MNG FUT has its own bounded startup waits. Keep UI responsive until it exits.
        while (-not $worker.HasExited) {
            Wait-Ui 300; Refresh-ServerLogs
            $ready = Read-JsonFile (Join-Path $root 'runtime\status.json')
            if ($ready.connection -like 'WAITING EXTERNAL GAME*' -and (Test-ManagedServerRunning '21')) { break }
            if ((Test-Mng21GamePrepared @(Get-Process -Name FIFA21 -ErrorAction SilentlyContinue) $ready $exe) -and (Test-ManagedServerRunning '21')) { break }
        }
        if ($worker.HasExited -and $null -ne $worker.ExitCode -and $worker.ExitCode -ne 0) { throw "MNG FUT n’a pas terminé la préparation (code $($worker.ExitCode)). Consulte les journaux FIFA 21." }
        $status = Read-JsonFile (Join-Path $root 'runtime\status.json')
        if (-not (Test-ManagedServerRunning '21') -or -not $status) { throw "Le serveur MNG FUT n'est pas prêt. Consulte les journaux FIFA 21." }
        $script:ActiveServerGame = '21'
        Set-OperationStatus 'Serveur démarré. Lance FIFA 21 avec ton lanceur habituel.' '#87DB72'
    } finally { $script:Fifa21Starting = $false; Apply-Language; Refresh-ServerLogs }
}
function Launch-SelectedGame {
    if ($script:SelectedGame -ne '21') { Launch-LegacySelectedGame; return }
    try {
        if ($script:Fifa21Starting -or $script:Fifa21Stopping) { return }
        if (-not (Test-GameExe (Get-SelectedGameExe))) { Choose-GameExe; return }
        Start-Fifa21Server
        if (-not (Test-ManagedServerRunning '21')) { return }
        if (Get-Process -Name FIFA21 -ErrorAction SilentlyContinue) {
            Set-OperationStatus 'FIFA 21 est déjà ouvert.' '#87DB72'; return
        }
        # Use the same EA App offer as the connector, preserving normal EA authentication.
        $root = Get-Mng21Root
        . (Join-Path $root 'User-Settings.ps1')
        $userSettings = Get-LocalFutUserSettings (Resolve-LocalFutUserConfigRoot)
        $offerId = [string]$userSettings.eaAppOfferId
        if ($offerId -notmatch '^\d+$') { throw 'Le jeu FIFA 21 configuré dans EA App est invalide.' }
        $uri = 'origin2://game/launch/?offerIds='+$offerId+'&authCode=&cmdParams='
        if ($userSettings.eaAppLauncherPath) {
            if (-not (Test-Path -LiteralPath $userSettings.eaAppLauncherPath -PathType Leaf)) { throw 'EA App est introuvable au chemin configuré.' }
            Start-Process -FilePath $userSettings.eaAppLauncherPath -ArgumentList $uri | Out-Null
        } else {
            $launch = New-Object Diagnostics.ProcessStartInfo
            $launch.FileName = $uri; $launch.UseShellExecute = $true
            [Diagnostics.Process]::Start($launch) | Out-Null
        }
        Set-OperationStatus 'Lancement de FIFA 21 demandé à EA App…' '#87DB72'
    } catch { Set-OperationStatus $_.Exception.Message '#E76F6F' }
}
function Stop-SelectedServer {
    if ($script:SelectedGame -ne '21') { Stop-LegacySelectedServer; return }
    if ($script:Fifa21Starting) { return }
    if ($script:Fifa21Stopping) { return }
    $script:Fifa21Stopping = $true
    try {
        $root = Get-Mng21Root
        Apply-Language
        Set-OperationStatus "Arrêt du serveur en cours…"
        $stopLog = Join-Path $root 'runtime\mng-stop.log'
        $stop = Start-Mng21BackgroundWorker ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -LauncherLogPath "{1}"' -f (Join-Path $root 'Stop-LocalFUT.ps1'),$stopLog) $root
        $null = $stop.Handle
        while (-not $stop.HasExited) { Wait-Ui 100 }
        if ($null -ne $stop.ExitCode -and $stop.ExitCode -ne 0) { throw "MNG FUT n'a pas pu arrêter la session. Consulte ses journaux." }
        $status = Read-JsonFile (Join-Path $root 'runtime\status.json')
        if (-not $status -or $status.server -ne 'STOPPED') { throw "L'arrêt du serveur n'est pas confirmé. Consulte mng-stop.log." }
        $script:ActiveServerGame = ''
        Set-OperationStatus 'SERVEUR ARRÊTÉ — FIFA 21 reste ouvert.' '#87DB72'
    } catch { Set-OperationStatus "Échec de l'arrêt du serveur" '#E76F6F'; [Windows.MessageBox]::Show($_.Exception.Message,'MNG FUT') | Out-Null }
    finally { $script:Fifa21Stopping = $false; Apply-Language; Refresh-ServerLogs }
}
function Show-Fifa21Preparation {
    Set-OperationStatus "FIFA 21 utilise MNG FUT. Lance la session depuis l'accueil MNG FUT."
}

# Native FIFA 21 interface. Embedded into MNG-FUT.ps1 by build-launcher.py.
[xml]$xaml=@'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Title="MNG FUT — FIFA 21" Width="1080" Height="720" MinWidth="920" MinHeight="660" WindowStartupLocation="CenterScreen" Background="#10101A" Foreground="#F6F5FF" FontFamily="Segoe UI">
 <Window.Resources>
  <Style TargetType="Button">
   <Setter Property="Foreground" Value="#F6F5FF"/><Setter Property="Background" Value="#272435"/><Setter Property="BorderThickness" Value="0"/><Setter Property="Padding" Value="20,13"/><Setter Property="FontSize" Value="14"/><Setter Property="FontWeight" Value="SemiBold"/><Setter Property="Cursor" Value="Hand"/>
   <Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button"><Border x:Name="Surface" Background="{TemplateBinding Background}" CornerRadius="9" Padding="{TemplateBinding Padding}"><ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Surface" Property="Opacity" Value="0.8"/></Trigger><Trigger Property="IsEnabled" Value="False"><Setter TargetName="Surface" Property="Opacity" Value="0.4"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Setter.Value></Setter>
  </Style>
  <Style TargetType="TextBox"><Setter Property="Background" Value="#12121E"/><Setter Property="Foreground" Value="White"/><Setter Property="BorderBrush" Value="#444053"/><Setter Property="Padding" Value="12"/><Setter Property="FontSize" Value="16"/><Setter Property="CaretBrush" Value="#CEFA52"/></Style>
  <Style TargetType="PasswordBox"><Setter Property="Background" Value="#12121E"/><Setter Property="Foreground" Value="White"/><Setter Property="BorderBrush" Value="#444053"/><Setter Property="Padding" Value="12"/><Setter Property="FontSize" Value="16"/><Setter Property="CaretBrush" Value="#CEFA52"/></Style>
 </Window.Resources>
 <Grid Margin="32,24" Background="#10101A" TextElement.Foreground="#F6F5FF" TextElement.FontFamily="Segoe UI">
  <Grid.RowDefinitions><RowDefinition Height="64"/><RowDefinition Height="*"/><RowDefinition Height="44"/></Grid.RowDefinitions>
  <DockPanel><StackPanel DockPanel.Dock="Left" Orientation="Horizontal" VerticalAlignment="Center"><TextBlock Text="MNG" FontSize="29" FontWeight="Black" Foreground="#CEFA52"/><TextBlock Text=" FUT" FontSize="29" FontWeight="Light"/><Border Background="#302540" CornerRadius="5" Margin="14,0,0,0" Padding="9,4" VerticalAlignment="Center"><TextBlock Text="FIFA 21" FontSize="11" Foreground="#C9B0FF" FontWeight="Bold"/></Border></StackPanel><StackPanel Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Center"><TextBlock x:Name="AccountStatus" Margin="0,0,16,0" VerticalAlignment="Center" Foreground="#B3AEC3"/><Button x:Name="SettingsButton" Content="⚙  Réglages"/></StackPanel></DockPanel>
  <Grid Grid.Row="1">
   <Grid x:Name="AuthView" Margin="0,25,0,8">
    <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="420"/></Grid.ColumnDefinitions>
    <Border Margin="0,0,30,0" CornerRadius="18" Padding="30"><Border.Background><LinearGradientBrush StartPoint="0,0" EndPoint="1,1"><GradientStop Color="#593299" Offset="0"/><GradientStop Color="#221835" Offset="1"/></LinearGradientBrush></Border.Background><Grid><StackPanel VerticalAlignment="Center"><TextBlock Text="LE FOOTBALL.&#10;VOTRE CLUB.&#10;VOTRE HISTOIRE." FontSize="38" FontWeight="Black" LineHeight="48"/><Rectangle Height="5" Width="62" Fill="#CEFA52" HorizontalAlignment="Left" Margin="0,25,0,25"/><TextBlock Text="Retrouvez Ultimate Team sur MNG FUT." FontSize="16" TextWrapping="Wrap" Foreground="#DDD0F0"/><TextBlock Text="Vos joueurs, vos crédits et votre progression&#10;liés à votre compte MNG." FontSize="14" LineHeight="24" Foreground="#BAA8D2" Margin="0,12,0,0"/></StackPanel><TextBlock Text="MNG FUT  /  FIFA 21" VerticalAlignment="Bottom" Foreground="#BDA8D5" FontSize="11"/></Grid></Border>
    <Border Grid.Column="1" Background="#1C1A29" CornerRadius="18" Padding="30"><ScrollViewer VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Disabled"><StackPanel VerticalAlignment="Center">
     <Grid Margin="0,0,0,25"><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions><Button x:Name="LoginTab" Content="Se connecter" Background="#7842DD" Margin="0,0,5,0" Padding="8,12"/><Button x:Name="RegisterTab" Grid.Column="1" Content="Créer un compte" Padding="8,12"/></Grid>
     <TextBlock x:Name="AuthTitle" Text="Bon retour sur MNG FUT" FontSize="23" FontWeight="Bold"/><TextBlock x:Name="AuthDescription" Text="Connectez-vous pour retrouver votre club." Foreground="#A9A3BA" Margin="0,9,0,24" TextWrapping="Wrap"/>
     <TextBlock Text="Nom d’utilisateur" Foreground="#D3CDDF" Margin="0,0,0,8"/><TextBox x:Name="LoginUserBox" MaxLength="64"/>
     <TextBlock Text="Mot de passe" Foreground="#D3CDDF" Margin="0,17,0,8"/>
     <Grid><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
      <PasswordBox x:Name="LoginPasswordBox" MaxLength="256"/>
      <TextBox x:Name="VisiblePasswordBox" MaxLength="256" Visibility="Collapsed"/>
      <Button x:Name="TogglePasswordButton" Grid.Column="1" Content="Afficher" ToolTip="Afficher le mot de passe" Margin="8,0,0,0" Padding="12,10" FontSize="12"/>
     </Grid>
     <CheckBox x:Name="RememberCheckBox" Content="Rester connecté" Foreground="#D3CDDF" FontSize="13" Margin="0,18,0,18"/>
     <Button x:Name="LoginSubmitButton" Content="Se connecter" Background="#CEFA52" Foreground="#15151D"/>
     <TextBlock x:Name="LoginMessage" Foreground="#E8A6B6" TextWrapping="Wrap" Margin="0,14,0,0" MinHeight="38"/>
    </StackPanel></ScrollViewer></Border>
   </Grid>
   <Grid x:Name="HomeView" Visibility="Collapsed" Margin="0,25,0,8">
    <Grid.RowDefinitions><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
    <Border CornerRadius="18" ClipToBounds="True" Background="#2B1746"><Grid>
     <Image x:Name="HeroImage" Stretch="UniformToFill" Opacity="0.27"/>
     <Border><Border.Background><LinearGradientBrush StartPoint="0,0" EndPoint="1,0"><GradientStop Color="#F0171029" Offset="0"/><GradientStop Color="#40171029" Offset="1"/></LinearGradientBrush></Border.Background></Border>
     <TextBlock Text="21" FontSize="250" FontWeight="Black" Foreground="#8862C3" Opacity="0.24" HorizontalAlignment="Right" VerticalAlignment="Center" Margin="0,0,35,0"/>
     <StackPanel Margin="38" VerticalAlignment="Center"><TextBlock Text="ULTIMATE TEAM" Foreground="#CEFA52" FontSize="13" FontWeight="Bold"/><TextBlock Text="FIFA 21" FontSize="70" FontWeight="Black" Margin="-3,0,0,3"/><TextBlock Text="Votre club vous attend." FontSize="22" Foreground="#E2D8EE"/><TextBlock x:Name="GameHeaderText" Text="FIFA 21 • SERVEUR EN LIGNE" Foreground="#B8A9CD" Margin="0,24,0,0" FontSize="12"/></StackPanel>
    </Grid></Border>
    <Border Grid.Row="1" Background="#1C1A29" CornerRadius="14" Margin="0,16,0,0" Padding="24"><StackPanel>
     <Grid><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions><Button x:Name="PlayButton" Content="Lancer le serveur" Background="#7842DD" Margin="0,0,8,0"/><Button x:Name="LaunchGameButton" Grid.Column="1" Content="Choisir exe" Background="#CEFA52" Foreground="#15151D" Margin="8,0,0,0"/></Grid>
     <TextBlock x:Name="GamePathText" Foreground="#A9A3BA" FontSize="11" Margin="0,16,0,0" TextTrimming="CharacterEllipsis"/>
    </StackPanel></Border>
   </Grid>
  </Grid>
  <DockPanel Grid.Row="2" Margin="0,10,0,0"><TextBlock x:Name="VersionText" DockPanel.Dock="Right" Foreground="#756E88" VerticalAlignment="Center"/><TextBlock x:Name="LaunchStatus" Text="Bienvenue sur MNG FUT" Foreground="#AFA7C2" VerticalAlignment="Center" TextTrimming="CharacterEllipsis"/></DockPanel>
  <Border x:Name="SettingsDrawer" Grid.RowSpan="3" Background="#EE10101A" Visibility="Collapsed"><Border Background="#211D30" CornerRadius="18" Width="510" Padding="32" HorizontalAlignment="Right" VerticalAlignment="Stretch"><StackPanel>
   <DockPanel Margin="0,0,0,32"><Button x:Name="CloseSettingsButton" Content="Fermer" DockPanel.Dock="Right" Padding="14,9"/><TextBlock Text="Réglages" FontSize="27" FontWeight="Bold"/></DockPanel>
   <TextBlock Text="LANCEUR MNG FUT" Foreground="#C3A5F1" FontWeight="Bold" FontSize="11"/><TextBlock x:Name="SettingsVersion" Margin="0,10,0,18" Foreground="#D3CDDF"/>
   <Button x:Name="AppUpdateButton" Content="Rechercher une mise à jour" Background="#7842DD"/>
   <TextBlock x:Name="UpdateStatusText" TextWrapping="Wrap" Foreground="#CEFA52" Margin="0,12,0,0"/>
   <TextBlock Text="Les mises à jour du lanceur sont vérifiées avant leur installation." Foreground="#AFA7C2" TextWrapping="Wrap" Margin="0,12,0,28"/>
   <TextBlock Text="FIFA 21" Foreground="#C3A5F1" FontWeight="Bold" FontSize="11"/><Button x:Name="ChangeFolderButton" Content="Changer l’exécutable FIFA 21" Margin="0,12,0,12"/>
   <TextBlock x:Name="SettingsHint" Text="Choisissez FIFA21.exe dans le dossier du jeu." TextWrapping="Wrap" Foreground="#AFA7C2" Margin="0,0,0,24"/>
   <Button x:Name="LogoutButton" Content="Se déconnecter du compte" Foreground="#F2B1C4"/>
  </StackPanel></Border></Border>
  <TextBox x:Name="ServerLogsBox" Visibility="Collapsed"/>
 </Grid>
</Window>
'@
$window=[Windows.Markup.XamlReader]::Load((New-Object Xml.XmlNodeReader $xaml))
function C([string]$name){return $window.FindName($name)}
foreach($name in @('AuthView','HomeView','AccountStatus','SettingsButton','LoginTab','RegisterTab','AuthTitle','AuthDescription','LoginUserBox','LoginPasswordBox','RememberCheckBox','LoginSubmitButton','LoginMessage','HeroImage','GameHeaderText','PlayButton','LaunchGameButton','GamePathText','VersionText','LaunchStatus','SettingsDrawer','CloseSettingsButton','SettingsVersion','AppUpdateButton','UpdateStatusText','ChangeFolderButton','SettingsHint','LogoutButton','ServerLogsBox')){Set-Variable -Name $name -Value (C $name)}
$VersionText.Text='v'+$script:LauncherVersion
$SettingsVersion.Text='Version installée : '+$script:LauncherVersion
$hero=Join-Path $script:AppRoot 'assets\hero.jpg'
if(Test-Path -LiteralPath $hero){$HeroImage.Source=[Windows.Media.Imaging.BitmapImage]::new([Uri]$hero)}
$script:AuthMode='login'
$VisiblePasswordBox=C 'VisiblePasswordBox';$TogglePasswordButton=C 'TogglePasswordButton'
function Set-PasswordVisible([bool]$Visible){
 if($Visible){
  $VisiblePasswordBox.Text=$LoginPasswordBox.Password
  $LoginPasswordBox.Visibility='Collapsed';$VisiblePasswordBox.Visibility='Visible'
  $TogglePasswordButton.Content='Masquer';$TogglePasswordButton.ToolTip='Masquer le mot de passe'
  $VisiblePasswordBox.Focus() | Out-Null;$VisiblePasswordBox.CaretIndex=$VisiblePasswordBox.Text.Length
 }else{
  $VisiblePasswordBox.Visibility='Collapsed';$LoginPasswordBox.Visibility='Visible';$VisiblePasswordBox.Clear()
  $TogglePasswordButton.Content='Afficher';$TogglePasswordButton.ToolTip='Afficher le mot de passe'
 }
}
$TogglePasswordButton.Add_Click({Set-PasswordVisible ($VisiblePasswordBox.Visibility -ne 'Visible')})
$VisiblePasswordBox.Add_TextChanged({if($VisiblePasswordBox.Visibility -eq 'Visible' -and $LoginPasswordBox.Password -cne $VisiblePasswordBox.Text){$LoginPasswordBox.Password=$VisiblePasswordBox.Text}})
$LoginPasswordBox.Add_PasswordChanged({if($VisiblePasswordBox.Visibility -eq 'Visible' -and $VisiblePasswordBox.Text -cne $LoginPasswordBox.Password){$VisiblePasswordBox.Text=$LoginPasswordBox.Password}})
$VisiblePasswordBox.Add_KeyDown({param($sender,$eventArgs) if($eventArgs.Key -eq 'Return'){Submit-Account}})
$script:AuthBusy=$false
$script:RememberPath=Join-Path $script:StateRoot 'remembered-account.xml'
function Set-OperationStatus([string]$Text,[string]$Color='#E3CF66'){
 $LaunchStatus.Text='●  '+$Text;$LaunchStatus.Foreground=$Color
 if($SettingsDrawer.Visibility -eq 'Visible'){$UpdateStatusText.Text=$Text;$UpdateStatusText.Foreground=$Color}
 $window.Dispatcher.Invoke([action]{},[Windows.Threading.DispatcherPriority]::Background)
}
function Set-AuthMode([string]$Mode){
 Set-PasswordVisible $false
 $script:AuthMode=$Mode;$register=$Mode -eq 'register'
 $AuthTitle.Text=if($register){'Bienvenue sur MNG FUT'}else{'Bon retour sur MNG FUT'}
 $AuthDescription.Text=if($register){'Créez votre compte pour commencer votre club.'}else{'Connectez-vous pour retrouver votre club.'}
 $LoginSubmitButton.Content=if($register){'Créer mon compte'}else{'Se connecter'}
 $LoginTab.Background=if($register){'#272435'}else{'#7842DD'};$RegisterTab.Background=if($register){'#7842DD'}else{'#272435'}
 $LoginMessage.Text=''
}
function Save-RememberedSession {
 $settings=Get-Settings;Set-Property $settings 'RememberMe' ([bool]$RememberCheckBox.IsChecked);Write-JsonFile $script:SettingsPath $settings
 if($RememberCheckBox.IsChecked -and $script:Session){
  # Windows DPAPI binds the remembered token to this Windows user. Never save passwords.
  [pscustomobject]@{apiBaseUrl=$script:Session.apiBaseUrl;token=(ConvertTo-SecureString ([string]$script:Session.token) -AsPlainText -Force)} | Export-Clixml -LiteralPath $script:RememberPath
 }else{Remove-Item -LiteralPath $script:RememberPath -Force -ErrorAction SilentlyContinue}
}
function Restore-RememberedSession {
 if(-not (Get-Settings).RememberMe -or -not (Test-Path -LiteralPath $script:RememberPath)){return $false}
 try{
  $saved=Import-Clixml -LiteralPath $script:RememberPath
  $credential=New-Object Management.Automation.PSCredential('MNG',$saved.token)
  $session=[pscustomobject]@{apiBaseUrl=$saved.apiBaseUrl;token=$credential.GetNetworkCredential().Password}
  Write-JsonFile $script:SessionPath $session
  return (Validate-Session)
 }catch{$LoginMessage.Text='Reconnectez-vous pour retrouver votre club.';return $false}
}
function Update-AccountUi {
 $connected=$null -ne $script:Profile
 $AuthView.Visibility=if($connected){'Collapsed'}else{'Visible'};$HomeView.Visibility=if($connected){'Visible'}else{'Collapsed'}
 $AccountStatus.Text=if($connected){[string]$script:Profile.username}else{''}
 $LogoutButton.IsEnabled=$connected;$ChangeFolderButton.IsEnabled=$connected
 Apply-Language
}
function Open-Account {$script:Profile=$null;Update-AccountUi}
function Get-SelectedGameExe {return [string](Get-Settings).Fifa21Exe}
function Test-GameExe([string]$Path){return ($Path -and [IO.Path]::GetFileName($Path) -ieq 'FIFA21.exe' -and (Test-Path -LiteralPath $Path -PathType Leaf))}
function Choose-GameExe {
 $dialog=New-Object Windows.Forms.OpenFileDialog;$dialog.Title='Choisir FIFA21.exe';$dialog.Filter='FIFA 21 (FIFA21.exe)|FIFA21.exe';$dialog.CheckFileExists=$true
 try{if($dialog.ShowDialog() -eq 'OK'){
  if(-not(Test-GameExe $dialog.FileName)){throw 'Choisissez le fichier FIFA21.exe du jeu.'}
  $settings=Get-Settings;Set-Property $settings 'Fifa21Exe' $dialog.FileName;Write-JsonFile $script:SettingsPath $settings
 }}finally{$dialog.Dispose();Apply-Language}
}
function Apply-Language {
 $busy=$script:Fifa21Starting -or $script:Fifa21Stopping -or $script:AuthBusy
 $PlayButton.Content='Lancer le serveur';$PlayButton.IsEnabled=(-not $busy -and $null -ne $script:Profile)
 $LaunchGameButton.Content=if(Test-GameExe (Get-SelectedGameExe)){'Lancer FIFA 21'}else{'Choisir exe'}
 $LaunchGameButton.IsEnabled=(-not $busy -and $null -ne $script:Profile)
 $GamePathText.Text=if(Test-GameExe (Get-SelectedGameExe)){Get-SelectedGameExe}else{'Sélectionnez FIFA21.exe pour lancer le jeu.'}
 $GamePathText.ToolTip=$GamePathText.Text
 $AppUpdateButton.IsEnabled=-not $busy;$ChangeFolderButton.IsEnabled=(-not $busy -and $null -ne $script:Profile);$LogoutButton.IsEnabled=(-not $busy -and $null -ne $script:Profile)
 $SettingsHint.Text='Choisissez FIFA21.exe dans le dossier du jeu. Votre choix est enregistré.'
}
function Submit-Account {
 if($script:AuthBusy){return}
 if([string]::IsNullOrWhiteSpace($LoginUserBox.Text) -or -not $LoginPasswordBox.Password){$LoginMessage.Text="Saisissez votre nom d’utilisateur et votre mot de passe.";return}
 $script:AuthBusy=$true;$LoginSubmitButton.IsEnabled=$false;$LoginTab.IsEnabled=$false;$RegisterTab.IsEnabled=$false
 $LoginMessage.Text=if($script:AuthMode -eq 'register'){'Création du compte…'}else{'Connexion…'};$window.Dispatcher.Invoke([action]{},[Windows.Threading.DispatcherPriority]::Background)
 try{
  $result=Try-AccountEndpoint $script:AuthMode $LoginUserBox.Text.Trim() $LoginPasswordBox.Password
  if($result.ok){Save-RememberedSession;$LoginPasswordBox.Clear();Set-PasswordVisible $false;Update-AccountUi;Set-OperationStatus 'Connecté à votre compte MNG FUT.' '#CEFA52'}else{$LoginMessage.Text=$result.message}
 }catch{$LoginMessage.Text=$_.Exception.Message}
 finally{$script:AuthBusy=$false;$LoginSubmitButton.IsEnabled=$true;$LoginTab.IsEnabled=$true;$RegisterTab.IsEnabled=$true;Apply-Language}
}
$LoginTab.Add_Click({Set-AuthMode 'login'});$RegisterTab.Add_Click({Set-AuthMode 'register'});$LoginSubmitButton.Add_Click({Submit-Account})
$LoginPasswordBox.Add_KeyDown({param($sender,$eventArgs) if($eventArgs.Key -eq 'Return'){Submit-Account}})
$SettingsButton.Add_Click({$SettingsDrawer.Visibility='Visible'});$CloseSettingsButton.Add_Click({$SettingsDrawer.Visibility='Collapsed'})
$AppUpdateButton.Add_Click({$AppUpdateButton.IsEnabled=$false;try{Update-ApplicationInternal}finally{$AppUpdateButton.IsEnabled=$true}})
$ChangeFolderButton.Add_Click({try{Choose-GameExe}catch{Set-OperationStatus $_.Exception.Message '#E8A6B6'}})
$PlayButton.Add_Click({try{Start-Fifa21Server}catch{Set-OperationStatus $_.Exception.Message '#E8A6B6'}finally{Apply-Language}})
$LaunchGameButton.Add_Click({if(-not(Test-GameExe (Get-SelectedGameExe))){Choose-GameExe}else{Launch-SelectedGame}})
$LogoutButton.Add_Click({
 try{
  # Disconnect the old club before changing the account used by the connector.
  if(Test-ManagedServerRunning '21'){Stop-SelectedServer;if(Test-ManagedServerRunning '21'){throw 'La session FUT est encore active. Réessayez la déconnexion.'}}
  Remove-Item -LiteralPath $script:RememberPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $script:SessionPath -Force -ErrorAction SilentlyContinue
  $script:Session=$null;$script:Profile=$null;$LoginPasswordBox.Clear();Set-PasswordVisible $false;$SettingsDrawer.Visibility='Collapsed';Update-AccountUi;Set-OperationStatus 'Vous êtes déconnecté.'
 }catch{Set-OperationStatus $_.Exception.Message '#E8A6B6'}
})
$window.Add_ContentRendered({
 $RememberCheckBox.IsChecked=[bool](Get-Settings).RememberMe
 Set-OperationStatus 'Bienvenue sur MNG FUT'
 if($RememberCheckBox.IsChecked){Set-OperationStatus 'Connexion à votre compte…';if(Restore-RememberedSession){Set-OperationStatus 'Votre compte est connecté.' '#CEFA52'}else{$LoginMessage.Text='Connexion automatique indisponible. Réessayez de vous connecter.'}}
 Update-AccountUi
})
Update-AccountUi
if($env:MNG_FUT_TEST_MODE -ne '1'){[void]$window.ShowDialog()}
