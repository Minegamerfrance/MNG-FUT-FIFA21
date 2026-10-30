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

function Get-AccountFailure($Failure){
    $status=0
    try{$status=[int]$Failure.Exception.Response.StatusCode}catch{}
    $body=[string]$Failure.ErrorDetails.Message
    if(-not $body -and $Failure.Exception.Response){
        try{
            $reader=New-Object IO.StreamReader($Failure.Exception.Response.GetResponseStream())
            try{$body=$reader.ReadToEnd()}finally{$reader.Dispose()}
        }catch{}
    }
    $payload=$null
    try{$payload=$body|ConvertFrom-Json -ErrorAction Stop}catch{}
    $message=switch([string]$payload.error){
        'INVALID_USERNAME' {"Nom d’utilisateur : 3 à 24 caractères (lettres, chiffres, _, . ou -)."}
        'INVALID_PASSWORD' {'Mot de passe : 8 à 128 caractères.'}
        'INVALID_CREDENTIALS' {"Nom d’utilisateur ou mot de passe incorrect."}
        'USERNAME_TAKEN' {"Ce nom d’utilisateur est déjà utilisé. Choisissez-en un autre ou connectez-vous."}
        default {
            if($payload.message){[string]$payload.message}
            elseif($status -in @(404,405)){'Le service de connexion est introuvable. Vérifiez les mises à jour du lanceur.'}
            elseif($status -eq 429){'Trop de tentatives. Patientez un peu avant de réessayer.'}
            elseif($status -ge 500){'Le service des comptes est temporairement indisponible. Réessayez dans un instant.'}
            elseif($status -eq 0){'Impossible de joindre le service des comptes. Vérifiez votre connexion et réessayez.'}
            else{'La demande a été refusée par le service des comptes (code '+$status+').'}
        }
    }
    return @{status=$status;message=$message}
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

                $last="La connexion n’a pas pu être vérifiée. Si vous venez de créer votre compte, essayez Se connecter."

            } else { $last='Réponse de connexion sans session. Réessayez de vous connecter.' }

            break

        }catch{

            $failure=Get-AccountFailure $_
            $last=$failure.message
            # Only try a legacy address when the route itself is unavailable.
            # A validation error or a taken username must never be replaced by
            # the legacy address's 404, nor cause a duplicate registration.
            if($failure.status -notin @(404,405)){break}

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
