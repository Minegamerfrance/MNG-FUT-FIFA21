$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../server/Launch-LocalFUT.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Resolve-Path $source), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
# Exercise the actual parameter attributes, including validation on assignment.
$probe = [scriptblock]::Create($ast.ParamBlock.Extent.Text + "`n" + '$RemoteHost = [Net.IPAddress]::Parse("149.56.212.60").IPAddressToString; $RemoteHost')
if ((& $probe) -ne '149.56.212.60') { throw 'Public account gateway address rejected' }
try { & $probe -RemoteHost 'https://invalid.example' | Out-Null; throw 'Malformed address accepted' }
catch [Management.Automation.ParameterBindingException] { }

$cleanup = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Remove-RedirectHostsEntry'}, $true)
Invoke-Expression $cleanup.Extent.Text
# Do not flush real DNS or access the real hosts file during this regression test.
function ipconfig { }
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('mng21-launcher-regression-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testRoot) | Out-Null
$HostsPath = Join-Path $testRoot 'hosts'
$expected = "# Keep this comment`r`n192.0.2.12 example.test`r`n"
$held = $null
try {
    [IO.File]::WriteAllText($HostsPath, $expected + "127.0.0.1 spring18.gosredirector.ea.com`r`n", [Text.UTF8Encoding]::new($false))
    $held = [IO.File]::Open($HostsPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    Remove-RedirectHostsEntry
    if ([IO.File]::ReadAllText($HostsPath) -cne $expected) { throw 'Cleanup changed unrelated hosts content' }
    Write-Output 'PASS: account gateway IPv4 accepted; malformed input rejected; shared-file cleanup preserves unrelated entries'
} finally {
    if ($held) { $held.Dispose() }
    if (Test-Path -LiteralPath $HostsPath) { Remove-Item -LiteralPath $HostsPath }
    Remove-Item -LiteralPath $testRoot
}
