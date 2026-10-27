# Dot-sourced by Launch-LocalFUT; no operation for an existing saved club.
function Initialize-Mng21NewClub($Python,[string]$ConfigRoot) {
    $savedRoot=if($env:LOCALFUT_RUNTIME_ROOT){$env:LOCALFUT_RUNTIME_ROOT}else{Join-Path $env:LOCALAPPDATA 'FIFA21LocalFUT'}
    $helper=Join-Path $PSScriptRoot 'first_run.py'
    $check=& $Python.Path @($Python.Arguments) $helper --runtime-root $savedRoot --config-root $ConfigRoot
    if($LASTEXITCODE -ne 0){throw 'Impossible de vérifier le profil FIFA 21.'}
    if(($check|ConvertFrom-Json).ready){return}
    Add-Type -AssemblyName PresentationFramework
    $view=[Windows.Markup.XamlReader]::Parse(@'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Title="Bienvenue dans MNG FUT 21" Width="440" Height="510" ResizeMode="NoResize" WindowStartupLocation="CenterScreen" Background="#181727" Foreground="White">
 <StackPanel Margin="28">
  <TextBlock Text="Crée ton club" FontSize="28" Foreground="#25F5C5" Margin="0,0,0,12"/>
  <TextBlock Text="23 joueurs bronze · 10 000 crédits · 1 000 points FIFA" TextWrapping="Wrap" Margin="0,0,0,18"/>
  <TextBlock Text="Ton pseudo"/><TextBox x:Name="Nickname" MaxLength="24" Margin="0,5,0,12" Padding="7"/>
  <TextBlock Text="Nom du club"/><TextBox x:Name="ClubName" MaxLength="24" Margin="0,5,0,12" Padding="7"/>
  <TextBlock Text="Abréviation (2 à 5 lettres ou chiffres)"/><TextBox x:Name="Abbr" MaxLength="5" Margin="0,5,0,12" Padding="7"/>
  <TextBlock x:Name="Error" Foreground="#FF9A9A" TextWrapping="Wrap" Margin="0,0,0,8"/>
  <Button x:Name="Create" Content="Créer mon club" Padding="10" Background="#25F5C5" Foreground="#181727"/>
 </StackPanel>
</Window>
'@)
    $view.FindName('Create').Add_Click({
        $nickname=$view.FindName('Nickname').Text.Trim()
        $club=$view.FindName('ClubName').Text.Trim()
        $abbr=$view.FindName('Abbr').Text.Trim()
        if(!$nickname -or !$club -or !$abbr){$view.FindName('Error').Text='Renseigne ton pseudo, le nom du club et son abréviation.';return}
        $result=& $Python.Path @($Python.Arguments) $helper --runtime-root $savedRoot --config-root $ConfigRoot ('--nickname='+$nickname) ('--club-name='+$club) ('--abbr='+$abbr)
        if($LASTEXITCODE -ne 0){$view.FindName('Error').Text=($result|ConvertFrom-Json).error;return}
        $view.DialogResult=$true
    }.GetNewClosure())
    if($view.ShowDialog() -ne $true){throw 'Création du club annulée.'}
}
