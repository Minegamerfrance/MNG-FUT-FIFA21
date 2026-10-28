[CmdletBinding()]
param([string]$LauncherLogPath = '')

function Write-RuntimeText {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true,ValueFromPipeline=$true)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory=$true)][string]$Path
    )
    begin { $lines = New-Object 'Collections.Generic.List[string]' }
    process { $lines.Add($Text) }
    end {
        $destination = [IO.Path]::GetFullPath($Path)
        $folder = [IO.Path]::GetDirectoryName($destination)
        [IO.Directory]::CreateDirectory($folder) | Out-Null
        $temporary = Join-Path $folder ([IO.Path]::GetFileName($destination)+'.'+[guid]::NewGuid().ToString('N')+'.tmp')
        try {
            [IO.File]::WriteAllText($temporary,($lines -join [Environment]::NewLine),[Text.UTF8Encoding]::new($false))
            for ($attempt=0; $attempt -lt 40; $attempt++) {
                try {
                    if ([IO.File]::Exists($destination)) {
                        [IO.File]::Replace($temporary,$destination,[System.Management.Automation.Language.NullString]::Value)
                    } else {
                        [IO.File]::Move($temporary,$destination)
                    }
                    return
                } catch [IO.IOException] {
                    if ($attempt -eq 39) { throw }
                    Start-Sleep -Milliseconds 100
                }
            }
        } finally {
            if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        }
    }
}

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot 'runtime'
$PidPath = Join-Path $RuntimeRoot 'launcher-processes.json'
$VendorRoot = Join-Path $ProjectRoot 'runtime-source'
$HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$Pattern = '^\s*127\.0\.0\.1\s+spring18\.gosredirector\.(?:ea\.com|(?:stest|scert|sdev)\.ea\.com)\s*$'

function Test-ProcessOwnsScript([object]$ProcessInfo, [string]$ScriptPath, [string]$RelativeScriptPath = '') {
    if (-not $ProcessInfo -or -not $ScriptPath -or -not $ProcessInfo.CommandLine) { return $false }
    try {
        $expected = [IO.Path]::GetFullPath($ScriptPath).Replace('/', '\').ToLowerInvariant()
        $actual = ([string]$ProcessInfo.CommandLine).Replace('/', '\').ToLowerInvariant()
        if ($actual.Contains($expected)) { return $true }
        if ($RelativeScriptPath -and [string]$ProcessInfo.Name -match '^python(?:3)?(?:\.exe)?$') {
            $relative = $RelativeScriptPath.Replace('/', '\').ToLowerInvariant()
            $argumentPattern = '(?:^|[\s"])' + [regex]::Escape($relative) + '(?:[\s"]|$)'
            return $actual -match $argumentPattern
        }
        return $false
    } catch {
        return $false
    }
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath))
    if ($LauncherLogPath) { $arguments += @('-LauncherLogPath', ('"{0}"' -f $LauncherLogPath)) }
    $elevated = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $elevated.WaitForExit()
    exit $elevated.ExitCode
}

$transcribing = $false
try {
if ($LauncherLogPath) { Start-Transcript -LiteralPath $LauncherLogPath -Append -Force | Out-Null; $transcribing = $true }
if (Test-Path -LiteralPath $PidPath) {
    $tracked = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
    $trackedScripts = @(
        [pscustomobject]@{ Name = 'externalWaitPid'; FullPath = (Join-Path $ProjectRoot 'Launch-LocalFUT.ps1'); RelativePath = '' },
        [pscustomobject]@{ Name = 'serverPid'; FullPath = (Join-Path $VendorRoot 'localfut21\server.py'); RelativePath = 'localfut21\server.py' },
        [pscustomobject]@{ Name = 'serverPid'; FullPath = (Join-Path $VendorRoot 'remote_relay.py'); RelativePath = 'remote_relay.py' },
        [pscustomobject]@{ Name = 'redirectorPid'; FullPath = (Join-Path $VendorRoot 'redirector_tls.py'); RelativePath = 'redirector_tls.py' }
    )
    foreach ($trackedScript in $trackedScripts) {
        $id = [int]$tracked.($trackedScript.Name)
        $processInfo = if ($id -gt 0) { Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue } else { $null }
        if ($processInfo -and (Test-ProcessOwnsScript $processInfo $trackedScript.FullPath $trackedScript.RelativePath)) {
            Stop-Process -Id $id -Force
            Write-Host "Stopped tracked $($trackedScript.Name) process $id."
        }
    }
} else {
    Write-Host "No tracked launcher processes were found; checking for this launcher's orphaned local-runtime processes."
}

# A failed start can occur after the services are created but before their PIDs
# are saved. Restrict fallback cleanup to Python processes whose command line
# names one of this project's two runtime entry points.
$ownedScripts = @(
    [pscustomobject]@{ FullPath = (Join-Path $VendorRoot 'localfut21\server.py'); RelativePath = 'localfut21\server.py' },
    [pscustomobject]@{ FullPath = (Join-Path $VendorRoot 'remote_relay.py'); RelativePath = 'remote_relay.py' },
    [pscustomobject]@{ FullPath = (Join-Path $VendorRoot 'redirector_tls.py'); RelativePath = 'redirector_tls.py' }
)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    $processInfo = $_
    $owned = $ownedScripts | Where-Object { Test-ProcessOwnsScript $processInfo $_.FullPath $_.RelativePath }
    if ($owned) {
        Stop-Process -Id $processInfo.ProcessId -Force
        Write-Host "Stopped orphaned local-runtime process $($processInfo.ProcessId)."
    }
}

# Set-Content opens hosts without write sharing. Windows may already hold a
# shared handle on it; open explicitly with ReadWrite sharing and retry short
# transient locks. Read and edit through the same handle, preserving other lines.
for ($hostsAttempt = 0; $hostsAttempt -lt 8; $hostsAttempt++) {
    $hostsStream = $null
    try {
        $hostsStream = [IO.File]::Open($HostsPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
        $reader = [IO.StreamReader]::new($hostsStream, [Text.Encoding]::UTF8, $true, 1024, $true)
        try { $hostsText = $reader.ReadToEnd() } finally { $reader.Dispose() }
        $hostsLines = [regex]::Split($hostsText, '(?<=\n)')
        $filteredText = ($hostsLines | Where-Object { $_.TrimEnd("`r", "`n") -notmatch $Pattern }) -join ''
        if ($filteredText -cne $hostsText) {
            $hostsBytes = [Text.UTF8Encoding]::new($false).GetBytes($filteredText)
            $hostsStream.Position = 0
            $hostsStream.Write($hostsBytes, 0, $hostsBytes.Length)
            $hostsStream.SetLength($hostsBytes.Length)
            $hostsStream.Flush()
            Write-Host "Removed this launcher's FIFA redirector hosts entry."
        } else {
            Write-Host 'No FIFA redirector hosts entry was present.'
        }
        break
    } catch [IO.IOException] {
        if ($hostsAttempt -eq 7) { throw }
        Start-Sleep -Milliseconds 250
    } finally {
        if ($hostsStream) { $hostsStream.Dispose() }
    }
}
ipconfig /flushdns | Out-Null
$remaining = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -in @(8090,44321,42230) -and [string]$_.Address -in @('127.0.0.1','0.0.0.0','::','::1') })
if ($remaining) { throw ('Des services utilisent encore les ports FIFA 21 : '+(($remaining | ForEach-Object Port | Sort-Object -Unique) -join ', ')) }
if (Test-Path -LiteralPath $PidPath) { Remove-Item -LiteralPath $PidPath -Force }
$statusPath = Join-Path $RuntimeRoot 'status.json'
$status = if (Test-Path -LiteralPath $statusPath) { Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
foreach ($pair in @(@('server','STOPPED'),@('connection','OFFLINE - server stopped; game left open'),@('updatedAt',(Get-Date -Format o)))) {
    $status | Add-Member -NotePropertyName $pair[0] -NotePropertyValue $pair[1] -Force
}
$status | ConvertTo-Json -Depth 20 | Write-RuntimeText -Path $statusPath
Write-Host 'MNG FUT FIFA 21: arrêt du serveur confirmé. Le jeu reste ouvert.'
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    exit 1
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
}
