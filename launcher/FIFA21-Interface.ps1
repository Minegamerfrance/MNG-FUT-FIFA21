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
     <TextBlock x:Name="PasswordRulesText" Text="8 à 128 caractères" Foreground="#A9A3BA" FontSize="11" Margin="0,7,0,0" Visibility="Collapsed"/>
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
$PasswordRulesText=C 'PasswordRulesText'
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
 $PasswordRulesText.Visibility=if($register){'Visible'}else{'Collapsed'}
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
function Update-ServerButton {
 $busy=$script:Fifa21Starting -or $script:Fifa21Stopping -or $script:AuthBusy
 $running=$false
 if($script:Profile -and -not $busy){$running=Test-ManagedServerRunning '21'}
 $PlayButton.Content=if($script:Fifa21Starting){'Démarrage…'}elseif($script:Fifa21Stopping){'Arrêt…'}elseif($running){'Arrêter le serveur'}else{'Lancer le serveur'}
 $PlayButton.IsEnabled=(-not $busy -and $null -ne $script:Profile)
 $GameHeaderText.Text=if($script:Fifa21Starting){'FIFA 21 • DÉMARRAGE EN COURS'}elseif($script:Fifa21Stopping){'FIFA 21 • ARRÊT EN COURS'}elseif($running){'FIFA 21 • SERVEUR DÉMARRÉ'}else{'FIFA 21 • SERVEUR ARRÊTÉ'}
}
function Toggle-Server {
 if(-not $script:Profile -or $script:Fifa21Starting -or $script:Fifa21Stopping -or $script:AuthBusy){return}
 try{if(Test-ManagedServerRunning '21'){Stop-SelectedServer}else{Start-Fifa21Server}}
 catch{Set-OperationStatus $_.Exception.Message '#E8A6B6'}
 finally{Apply-Language}
}
function Apply-Language {
 $busy=$script:Fifa21Starting -or $script:Fifa21Stopping -or $script:AuthBusy
 Update-ServerButton
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
 if($script:AuthMode -eq 'register'){
  if($LoginUserBox.Text.Trim() -notmatch '^[a-zA-Z0-9_.-]{3,24}$'){$LoginMessage.Text="Nom d’utilisateur : 3 à 24 caractères (lettres, chiffres, _, . ou -).";return}
  if($LoginPasswordBox.Password.Length -lt 8 -or $LoginPasswordBox.Password.Length -gt 128){$LoginMessage.Text='Mot de passe : 8 à 128 caractères.';return}
 }
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
$PlayButton.Add_Click({Toggle-Server})
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
$serverStateTimer=New-Object Windows.Threading.DispatcherTimer
$serverStateTimer.Interval=[TimeSpan]::FromSeconds(5)
$serverStateTimer.Add_Tick({if($script:Profile -and -not ($script:Fifa21Starting -or $script:Fifa21Stopping -or $script:AuthBusy)){Update-ServerButton}})
$window.Add_Closed({$serverStateTimer.Stop()})
$window.Add_ContentRendered({
 $RememberCheckBox.IsChecked=[bool](Get-Settings).RememberMe
 Set-OperationStatus 'Bienvenue sur MNG FUT'
 if($RememberCheckBox.IsChecked){Set-OperationStatus 'Connexion à votre compte…';if(Restore-RememberedSession){Set-OperationStatus 'Votre compte est connecté.' '#CEFA52'}else{$LoginMessage.Text='Connexion automatique indisponible. Réessayez de vous connecter.'}}
 Update-AccountUi
 $serverStateTimer.Start()
})
Update-AccountUi
if($env:MNG_FUT_TEST_MODE -ne '1'){[void]$window.ShowDialog()}
