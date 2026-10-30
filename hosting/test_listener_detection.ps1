$ErrorActionPreference='Stop'
$cases=@(@{Path='../server/Launch-LocalFUT.ps1';Name='Get-Listener'},@{Path='../launcher/MNG-FIFA21.ps1';Name='Get-Mng21Listener'})
foreach($case in $cases){
 $tokens=$null;$errors=$null
 $tree=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $case.Path),[ref]$tokens,[ref]$errors)
 if($errors){throw ($errors.Message -join "`n")}
 $definition=$tree.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $case.Name},$true)
 . ([scriptblock]::Create($definition.Extent.Text))
 function Get-NetTCPConnection {return $script:Rows}
 $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
 $listener.Start();$port=$listener.LocalEndpoint.Port
 try{
  $script:Rows=@([pscustomobject]@{LocalAddress='127.0.0.1';RemotePort=0;State='Closed';OwningProcess=4242})
  $actual=& $case.Name $port
  if(-not $actual -or $actual.OwningProcess -ne 4242){throw 'Accepting socket misreported as Closed was not detected with its owner.'}
  $script:Rows[0].State='Bound'
  if(-not (& $case.Name $port)){throw 'Accepting socket misreported as Bound was not detected.'}
  $script:Rows+= [pscustomobject]@{LocalAddress='127.0.0.1';RemotePort=0;State='Closed';OwningProcess=9999}
  if(& $case.Name $port){throw 'Ambiguous owners must not be guessed.'}
  $script:Rows=@([pscustomobject]@{LocalAddress='192.0.2.1';RemotePort=0;State='Listen';OwningProcess=4242})
  if(& $case.Name $port){throw 'Non-local listener accepted.'}
  $script:Rows=@([pscustomobject]@{LocalAddress='127.0.0.1';RemotePort=123;State='Established';OwningProcess=4242})
  if(& $case.Name $port){throw 'Connected client socket accepted as a listener.'}
 }finally{$listener.Stop()}
 $script:Rows=@([pscustomobject]@{LocalAddress='127.0.0.1';RemotePort=0;State='Closed';OwningProcess=4242})
 if(& $case.Name $port){throw 'Stopped socket accepted from a stale ownership row.'}
 Write-Output ('PASS: '+$case.Name+' detects mislabeled active sockets; rejects stale, ambiguous and non-local ownership.')
}
