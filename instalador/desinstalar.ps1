<#
  NOVA AI · Desinstalador
  Quita el programa de «Archivos de programa», sus accesos directos y su registro en Windows.
  Tus datos (ajustes, comandos, memoria, voces descargadas) se conservan salvo que marques borrarlos.

  Uso:  desinstalar.ps1               ventana con opciones
        desinstalar.ps1 -Silencioso   sin preguntas (conserva tus datos)
#>
param([switch]$Silencioso, [switch]$Copia, [string]$Root = '')
$ErrorActionPreference = 'Continue'
$AppName = 'NOVA AI'
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$DataRoot = Join-Path $env:LOCALAPPDATA $AppName
$RegKey = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NOVA AI'

function Get-Args([string]$file, [bool]$copy) {
    $a = '-NoProfile -ExecutionPolicy Bypass -STA -File "' + $file + '" -Root "' + $Root + '"'
    if ($copy) { $a += ' -Copia' }
    if ($Silencioso) { $a += ' -Silencioso' }
    return $a
}

# 1) Hacen falta permisos de administrador para tocar Archivos de programa y el registro.
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    try { Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList (Get-Args $PSCommandPath $false) -ErrorAction Stop } catch {}
    exit 0
}
# 2) Se ejecuta desde una copia en TEMP para poder borrar su propia carpeta.
if (-not $Copia) {
    $tmp = Join-Path $env:TEMP 'nova_ai_desinstalar.ps1'
    Copy-Item -LiteralPath $PSCommandPath -Destination $tmp -Force
    Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList (Get-Args $tmp $true)
    exit 0
}

# Seguridad: solo se borra una carpeta que de verdad es NOVA.
$looksRight = (Test-Path (Join-Path $Root 'nova.py')) -and (Test-Path (Join-Path $Root 'core\config.py'))

function Remove-Nova([bool]$deleteData, [scriptblock]$report) {
    & $report 'Cerrando NOVA AI si está abierta…'
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) -or
            ($_.CommandLine -and $_.CommandLine -like '*NOVA AI\datos\interfaz*')
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch {}
    Start-Sleep -Milliseconds 700

    & $report 'Quitando los accesos directos…'
    $desk = [Environment]::GetFolderPath('Desktop')
    $pub = [Environment]::GetFolderPath('CommonDesktopDirectory')
    foreach ($p in @((Join-Path $desk 'NOVA AI.lnk'), (Join-Path $pub 'NOVA AI.lnk'))) {
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue }
    }
    $menu = Join-Path ([Environment]::GetFolderPath('Programs')) $AppName
    if (Test-Path -LiteralPath $menu) { Remove-Item -LiteralPath $menu -Recurse -Force -ErrorAction SilentlyContinue }

    & $report 'Quitando NOVA AI de «Aplicaciones instaladas»…'
    if (Test-Path $RegKey) { Remove-Item -Path $RegKey -Recurse -Force -ErrorAction SilentlyContinue }

    & $report 'Borrando el programa…'
    for ($i = 0; $i -lt 6 -and (Test-Path -LiteralPath $Root); $i++) {
        Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $Root) { Start-Sleep -Seconds 1 }
    }
    if ($deleteData -and (Test-Path -LiteralPath $DataRoot)) {
        & $report 'Borrando tus datos…'
        Remove-Item -LiteralPath $DataRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    return (-not (Test-Path -LiteralPath $Root))
}

if ($Silencioso) {
    if ($looksRight) { [void](Remove-Nova $false { param($m) }) }
    exit 0
}

try {
    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml
} catch { exit 2 }

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Desinstalar NOVA AI" Width="620" Height="400" WindowStyle="None" AllowsTransparency="True"
        Background="Transparent" ResizeMode="NoResize" WindowStartupLocation="CenterScreen"
        FontFamily="Bahnschrift, Segoe UI" Foreground="#CFEFFF" UseLayoutRounding="True">
  <Window.Resources>
    <Style x:Key="Btn" TargetType="Button">
      <Setter Property="Foreground" Value="#DFF7FF"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Padding" Value="22,9"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="Bg" Background="#1A20B8E8" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="1" Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Bg" Property="Background" Value="#3320B8E8"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter TargetName="Bg" Property="Opacity" Value="0.35"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
      <Setter Property="BorderBrush" Value="#20B8E8"/>
    </Style>
  </Window.Resources>
  <Border Background="#F2040B14" BorderBrush="#6620B8E8" BorderThickness="1" CornerRadius="2">
    <Border.Effect><DropShadowEffect Color="#20B8E8" BlurRadius="24" ShadowDepth="0" Opacity="0.6"/></Border.Effect>
    <Grid Margin="30,24,30,22">
      <Grid.RowDefinitions>
        <RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/>
      </Grid.RowDefinitions>
      <StackPanel Orientation="Horizontal" x:Name="Header">
        <Image x:Name="Logo" Width="46" Height="46" Margin="0,0,14,0"/>
        <StackPanel VerticalAlignment="Center">
          <TextBlock Text="DESINSTALAR NOVA AI" FontSize="20" FontWeight="SemiBold" Foreground="#6FD8FF">
            <TextBlock.Effect><DropShadowEffect Color="#20B8E8" BlurRadius="12" ShadowDepth="0" Opacity="0.8"/></TextBlock.Effect>
          </TextBlock>
          <TextBlock Text="ASISTENTE DE VUELO PARA STAR CITIZEN" FontSize="10" Foreground="#20B8E8" Margin="0,2,0,0"/>
        </StackPanel>
      </StackPanel>
      <StackPanel Grid.Row="1" Margin="0,20,0,0">
        <TextBlock x:Name="Info" TextWrapping="Wrap" FontSize="14" LineHeight="21"/>
        <CheckBox x:Name="ChkData" Margin="0,16,0,0" Foreground="#CFEFFF" Cursor="Hand">
          <TextBlock TextWrapping="Wrap" Width="520">
            <Run Text="Borrar también mis datos"/>
            <Run x:Name="DataPath" Foreground="#6F93A8" FontSize="12"/>
          </TextBlock>
        </CheckBox>
        <TextBlock x:Name="Status" Margin="0,16,0,0" FontFamily="Consolas" FontSize="12" Foreground="#6FD8FF" TextWrapping="Wrap"/>
      </StackPanel>
      <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right">
        <Button x:Name="BtnCancel" Style="{StaticResource Btn}" Content="CANCELAR" Margin="0,0,12,0"/>
        <Button x:Name="BtnGo" Style="{StaticResource Btn}" Content="DESINSTALAR" BorderBrush="#FF6B7A"/>
      </StackPanel>
    </Grid>
  </Border>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Parse($xaml)
$ui = @{}
foreach ($n in 'Header', 'Logo', 'Info', 'ChkData', 'DataPath', 'Status', 'BtnCancel', 'BtnGo') { $ui[$n] = $window.FindName($n) }
try {
    $png = Join-Path $Root 'recursos\nova.png'
    if (Test-Path $png) {
        $bytes = [IO.File]::ReadAllBytes($png)  # en memoria: el archivo se va a borrar
        $bmp = New-Object Windows.Media.Imaging.BitmapImage
        $bmp.BeginInit(); $bmp.StreamSource = New-Object IO.MemoryStream (, $bytes); $bmp.CacheOption = 'OnLoad'; $bmp.EndInit()
        $ui.Logo.Source = $bmp
    }
} catch {}
$ui.Header.Add_MouseLeftButtonDown({ try { $window.DragMove() } catch {} })
$ui.DataPath.Text = "(ajustes, comandos propios, memoria, sesión y voces descargadas · $DataRoot)"

if ($looksRight) {
    $ui.Info.Text = "Se quitará NOVA AI de:`n$Root`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». " +
        "Si conservas tus datos, al reinstalar NOVA lo recordará todo."
} else {
    $ui.Info.Text = "No encuentro NOVA AI en:`n$Root`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro."
}

function Pump { $window.Dispatcher.Invoke([Action] {}, [Windows.Threading.DispatcherPriority]::Background) }
$report = { param($m) $ui.Status.Text = '▸ ' + $m; Pump }

$ui.BtnCancel.Add_Click({ $window.Close() })
$ui.BtnGo.Add_Click({
    if ($script:finished) { $window.Close(); return }
    $ui.BtnGo.IsEnabled = $false; $ui.BtnCancel.IsEnabled = $false; $ui.ChkData.IsEnabled = $false
    $ok = $true
    if ($looksRight) {
        $ok = Remove-Nova ([bool]$ui.ChkData.IsChecked) $report
    } else {
        $saved = $Root; $Root = Join-Path $env:TEMP 'nova-no-existe'
        [void](Remove-Nova ([bool]$ui.ChkData.IsChecked) $report); $Root = $saved
    }
    if ($ok) {
        $ui.Status.Text = '✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!'
        if (-not $ui.ChkData.IsChecked) { $ui.Status.Text += "`n  Tus datos siguen en $DataRoot por si vuelves." }
    } else {
        $ui.Status.Text = "⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: $Root"
        $ui.Status.Foreground = New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString('#E8C15A'))
    }
    $ui.BtnGo.Content = 'CERRAR'; $ui.BtnGo.IsEnabled = $true
    $script:finished = $true
})
$script:finished = $false
[void]$window.ShowDialog()
exit 0
