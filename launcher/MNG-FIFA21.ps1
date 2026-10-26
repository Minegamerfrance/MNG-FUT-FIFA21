
function Update-Mng21Package([switch]$CheckOnly,[switch]$Force) {
    $settings=Get-Settings
    $root=if($settings.Fifa21ServerRoot){[string]$settings.Fifa21ServerRoot}else{Join-Path $script:AppRoot 'fifa21-server'}
    if(-not [IO.Path]::IsPathRooted($root)){$root=Join-Path $script:AppRoot $root}
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
    if (-not (Test-Path -LiteralPath (Join-Path $root 'runtime-source\localfut21\server.py'))) { Update-Mng21Package }
    foreach ($file in @('Launch-LocalFUT.ps1','Stop-LocalFUT.ps1','User-Settings.ps1','runtime-source\localfut21\server.py')) {
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
        foreach ($entry in @(@{Port=8090;Script='localfut21\server.py'},@{Port=44321;Script='localfut21\server.py'},@{Port=42230;Script='redirector_tls.py'})) {
            $listener = Get-NetTCPConnection -State Listen -LocalPort $entry.Port -ErrorAction SilentlyContinue | Select-Object -First 1
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
                $hash = (Get-FileHash -LiteralPath (Join-Path $root ('runtime-source\localfut21\'+$pair[1])) -Algorithm SHA256).Hash
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
    $PlayButton.Content = T '▶   START SERVER' '▶   DÉMARRER LE SERVEUR' '▶   INICIAR SERVIDOR'
    if ($StopFifa21Button) {
        $StopFifa21Button.Content = T '■   STOP SERVER' '■   ARRÊTER LE SERVEUR' '■   DETENER SERVIDOR'
        $StopFifa21Button.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    }
    if ($GameHeaderText) { $GameHeaderText.Text = if ($script:Fifa21Starting) { 'FIFA 21 • PRÉPARATION EN COURS' } elseif ($running) { 'FIFA 21 • SERVEUR DÉMARRÉ' } else { 'FIFA 21 • SERVEUR ARRÊTÉ' } }
    $LaunchGameButton.Content = '▶   LANCER FIFA'
    $PlayButton.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    $LaunchGameButton.IsEnabled = -not ($script:Fifa21Starting -or $script:Fifa21Stopping)
    $SettingsHint.Text = 'Le serveur reste actif. Lance FIFA manuellement ; les nouvelles sessions sont détectées automatiquement.'
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
        Start-Fifa21Server
        Set-OperationStatus 'Serveur prêt. Lance FIFA 21 avec ton lanceur habituel.' '#87DB72'
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
if (Get-Command C -CommandType Function -ErrorAction SilentlyContinue) {
    $StopFifa21Button = C 'StopFifa21Button'
    $StopFifa21Button.Add_Click({ Stop-SelectedServer })
}
