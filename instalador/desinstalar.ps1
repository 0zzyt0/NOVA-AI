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
# v1.3: en el idioma de NOVA AI (el de tus ajustes)
$U = @{}
$h = New-Object Collections.Hashtable ([StringComparer]::Ordinal)
$h["Desinstalar NOVA AI"] = "Uninstall NOVA AI"
$h["DESINSTALAR NOVA AI"] = "UNINSTALL NOVA AI"
$h["ASISTENTE DE VUELO PARA STAR CITIZEN"] = "FLIGHT ASSISTANT FOR STAR CITIZEN"
$h["Borrar también mis datos (el Diccionario de consultas se conserva)"] = "Also delete my data (the lookup Dictionary is kept)"
$h["CANCELAR"] = "CANCEL"
$h["DESINSTALAR"] = "UNINSTALL"
$h["CERRAR"] = "CLOSE"
$h["Cerrando NOVA AI si está abierta…"] = "Closing NOVA AI if it's open…"
$h["Quitando los accesos directos…"] = "Removing the shortcuts…"
$h["Quitando NOVA AI de «Aplicaciones instaladas»…"] = "Removing NOVA AI from «Installed apps»…"
$h["Borrando el programa…"] = "Deleting the program…"
$h["Borrando tus datos…"] = "Deleting your data…"
$h["(ajustes, comandos propios, memoria, sesión y voces descargadas · {0})"] = "(settings, own commands, memory, session and downloaded voices · {0})"
$h["Se quitará NOVA AI de:`n{0}`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». Si conservas tus datos, al reinstalar NOVA lo recordará todo."] = "NOVA AI will be removed from:`n{0}`n`nAlso its shortcuts and its entry in «Installed apps». If you keep your data, NOVA will remember everything when reinstalled."
$h["No encuentro NOVA AI en:`n{0}`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro."] = "I can't find NOVA AI in:`n{0}`n`nIt may already be uninstalled. You can still remove the shortcuts and the registry entry."
$h["✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!"] = "✓ NOVA AI has been uninstalled. Fly safe, pilot!"
$h["`n  Tus datos siguen en {0} por si vuelves."] = "`n  Your data is still in {0} in case you come back."
$h["⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: {0}"] = "⚠ Some files were in use and couldn't be deleted.`n  Restart the PC and delete the folder manually: {0}"
$U['en'] = $h
$h = New-Object Collections.Hashtable ([StringComparer]::Ordinal)
$h["Desinstalar NOVA AI"] = "Desinstal·lar NOVA AI"
$h["DESINSTALAR NOVA AI"] = "DESINSTAL·LAR NOVA AI"
$h["ASISTENTE DE VUELO PARA STAR CITIZEN"] = "ASSISTENT DE VOL PER A STAR CITIZEN"
$h["Borrar también mis datos (el Diccionario de consultas se conserva)"] = "Esborrar també les meves dades (el Diccionari de consultes es conserva)"
$h["CANCELAR"] = "CANCEL·LAR"
$h["DESINSTALAR"] = "DESINSTAL·LAR"
$h["CERRAR"] = "TANCAR"
$h["Cerrando NOVA AI si está abierta…"] = "Tancant NOVA AI si està oberta…"
$h["Quitando los accesos directos…"] = "Traient els accessos directes…"
$h["Quitando NOVA AI de «Aplicaciones instaladas»…"] = "Traient NOVA AI d'«Aplicacions instal·lades»…"
$h["Borrando el programa…"] = "Esborrant el programa…"
$h["Borrando tus datos…"] = "Esborrant les teves dades…"
$h["(ajustes, comandos propios, memoria, sesión y voces descargadas · {0})"] = "(ajustos, ordres pròpies, memòria, sessió i veus descarregades · {0})"
$h["Se quitará NOVA AI de:`n{0}`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». Si conservas tus datos, al reinstalar NOVA lo recordará todo."] = "Es traurà NOVA AI de:`n{0}`n`nTambé els seus accessos directes i la seva entrada a «Aplicacions instal·lades». Si conserves les teves dades, en reinstal·lar NOVA ho recordarà tot."
$h["No encuentro NOVA AI en:`n{0}`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro."] = "No trobo NOVA AI a:`n{0}`n`nPot ser que ja estigui desinstal·lada. Igualment pots treure els accessos directes i el registre."
$h["✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!"] = "✓ NOVA AI s'ha desinstal·lat. Bon vol, pilot!"
$h["`n  Tus datos siguen en {0} por si vuelves."] = "`n  Les teves dades continuen a {0} per si tornes."
$h["⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: {0}"] = "⚠ Alguns fitxers estaven en ús i no s'han pogut esborrar.`n  Reinicia el PC i esborra a mà la carpeta: {0}"
$U['ca'] = $h
$h = New-Object Collections.Hashtable ([StringComparer]::Ordinal)
$h["Desinstalar NOVA AI"] = "Désinstaller NOVA AI"
$h["DESINSTALAR NOVA AI"] = "DÉSINSTALLER NOVA AI"
$h["ASISTENTE DE VUELO PARA STAR CITIZEN"] = "ASSISTANTE DE VOL POUR STAR CITIZEN"
$h["Borrar también mis datos (el Diccionario de consultas se conserva)"] = "Effacer aussi mes données (le Dictionnaire de consultations est conservé)"
$h["CANCELAR"] = "ANNULER"
$h["DESINSTALAR"] = "DÉSINSTALLER"
$h["CERRAR"] = "FERMER"
$h["Cerrando NOVA AI si está abierta…"] = "Fermeture de NOVA AI si elle est ouverte…"
$h["Quitando los accesos directos…"] = "Suppression des raccourcis…"
$h["Quitando NOVA AI de «Aplicaciones instaladas»…"] = "Retrait de NOVA AI des « Applications installées »…"
$h["Borrando el programa…"] = "Suppression du programme…"
$h["Borrando tus datos…"] = "Suppression de vos données…"
$h["(ajustes, comandos propios, memoria, sesión y voces descargadas · {0})"] = "(réglages, commandes personnelles, mémoire, session et voix téléchargées · {0})"
$h["Se quitará NOVA AI de:`n{0}`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». Si conservas tus datos, al reinstalar NOVA lo recordará todo."] = "NOVA AI sera retirée de :`n{0}`n`nAinsi que ses raccourcis et son entrée dans « Applications installées ». Si vous conservez vos données, NOVA se souviendra de tout à la réinstallation."
$h["No encuentro NOVA AI en:`n{0}`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro."] = "Je ne trouve pas NOVA AI dans :`n{0}`n`nElle est peut-être déjà désinstallée. Vous pouvez quand même retirer les raccourcis et l'entrée du registre."
$h["✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!"] = "✓ NOVA AI a été désinstallée. Bon vol, pilote !"
$h["`n  Tus datos siguen en {0} por si vuelves."] = "`n  Vos données restent dans {0} si vous revenez."
$h["⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: {0}"] = "⚠ Certains fichiers étaient utilisés et n'ont pas pu être supprimés.`n  Redémarrez le PC et supprimez le dossier à la main : {0}"
$U['fr'] = $h
$h = New-Object Collections.Hashtable ([StringComparer]::Ordinal)
$h["Desinstalar NOVA AI"] = "NOVA AI deinstallieren"
$h["DESINSTALAR NOVA AI"] = "NOVA AI DEINSTALLIEREN"
$h["ASISTENTE DE VUELO PARA STAR CITIZEN"] = "FLUGASSISTENTIN FÜR STAR CITIZEN"
$h["Borrar también mis datos (el Diccionario de consultas se conserva)"] = "Auch meine Daten löschen (das Abfrage-Wörterbuch bleibt erhalten)"
$h["CANCELAR"] = "ABBRECHEN"
$h["DESINSTALAR"] = "DEINSTALLIEREN"
$h["CERRAR"] = "SCHLIESSEN"
$h["Cerrando NOVA AI si está abierta…"] = "NOVA AI wird geschlossen, falls offen…"
$h["Quitando los accesos directos…"] = "Verknüpfungen werden entfernt…"
$h["Quitando NOVA AI de «Aplicaciones instaladas»…"] = "NOVA AI wird aus „Installierte Apps“ entfernt…"
$h["Borrando el programa…"] = "Programm wird gelöscht…"
$h["Borrando tus datos…"] = "Ihre Daten werden gelöscht…"
$h["(ajustes, comandos propios, memoria, sesión y voces descargadas · {0})"] = "(Einstellungen, eigene Befehle, Gedächtnis, Sitzung und heruntergeladene Stimmen · {0})"
$h["Se quitará NOVA AI de:`n{0}`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». Si conservas tus datos, al reinstalar NOVA lo recordará todo."] = "NOVA AI wird entfernt aus:`n{0}`n`nAuch ihre Verknüpfungen und ihr Eintrag in „Installierte Apps“. Wenn Sie Ihre Daten behalten, erinnert sich NOVA nach einer Neuinstallation an alles."
$h["No encuentro NOVA AI en:`n{0}`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro."] = "Ich finde NOVA AI nicht in:`n{0}`n`nVielleicht ist sie schon deinstalliert. Sie können trotzdem die Verknüpfungen und den Registrierungseintrag entfernen."
$h["✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!"] = "✓ NOVA AI wurde deinstalliert. Guten Flug, Pilot!"
$h["`n  Tus datos siguen en {0} por si vuelves."] = "`n  Ihre Daten bleiben in {0}, falls Sie zurückkommen."
$h["⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: {0}"] = "⚠ Einige Dateien waren in Benutzung und konnten nicht gelöscht werden.`n  Starten Sie den PC neu und löschen Sie den Ordner manuell: {0}"
$U['de'] = $h
$ULang = 'es'
try { $j = Get-Content -LiteralPath (Join-Path $DataRoot 'datos\ajustes.json') -Raw -Encoding UTF8 | ConvertFrom-Json; if ($j.idioma -and $U.ContainsKey([string]$j.idioma)) { $ULang = [string]$j.idioma } } catch {}
function T([string]$s) { if ($ULang -ne 'es' -and $U[$ULang][$s]) { return $U[$ULang][$s] }; return $s }
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
    & $report (T 'Cerrando NOVA AI si está abierta…')
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) -or
            ($_.CommandLine -and $_.CommandLine -like '*NOVA AI\datos\interfaz*')
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch {}
    Start-Sleep -Milliseconds 700

    & $report (T 'Quitando los accesos directos…')
    $desk = [Environment]::GetFolderPath('Desktop')
    $pub = [Environment]::GetFolderPath('CommonDesktopDirectory')
    foreach ($p in @((Join-Path $desk 'NOVA AI.lnk'), (Join-Path $pub 'NOVA AI.lnk'))) {
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue }
    }
    $menu = Join-Path ([Environment]::GetFolderPath('Programs')) $AppName
    if (Test-Path -LiteralPath $menu) { Remove-Item -LiteralPath $menu -Recurse -Force -ErrorAction SilentlyContinue }

    & $report (T 'Quitando NOVA AI de «Aplicaciones instaladas»…')
    if (Test-Path $RegKey) { Remove-Item -Path $RegKey -Recurse -Force -ErrorAction SilentlyContinue }

    & $report (T 'Borrando el programa…')
    for ($i = 0; $i -lt 6 -and (Test-Path -LiteralPath $Root); $i++) {
        Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $Root) { Start-Sleep -Seconds 1 }
    }
    if ($deleteData -and (Test-Path -LiteralPath $DataRoot)) {
        & $report (T 'Borrando tus datos…')
        # El Diccionario de consultas no se borra nunca: es la base offline de consultas entre versiones
        $dic = Join-Path $DataRoot 'datos\Diccionario_de_consultas.txt'
        $keep = $null
        if (Test-Path -LiteralPath $dic) {
            $keep = Join-Path $env:TEMP 'NOVA_AI_Diccionario_de_consultas.txt'
            try { Copy-Item -LiteralPath $dic -Destination $keep -Force } catch { $keep = $null }
        }
        Remove-Item -LiteralPath $DataRoot -Recurse -Force -ErrorAction SilentlyContinue
        if ($keep -and (Test-Path -LiteralPath $keep)) {
            New-Item -ItemType Directory -Force -Path (Split-Path $dic) | Out-Null
            Move-Item -LiteralPath $keep -Destination $dic -Force -ErrorAction SilentlyContinue
        }
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
            <Run Text="Borrar también mis datos (el Diccionario de consultas se conserva)"/>
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
$window.Title = T $window.Title
$ui.BtnCancel.Content = T $ui.BtnCancel.Content
$ui.BtnGo.Content = T $ui.BtnGo.Content
foreach ($tb in @($ui.Header.Children[1].Children)) { $tb.Text = T $tb.Text }
$ui.DataPath.PreviousInline.Text = T $ui.DataPath.PreviousInline.Text
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
$ui.DataPath.Text = (T "(ajustes, comandos propios, memoria, sesión y voces descargadas · {0})") -f $DataRoot

if ($looksRight) {
    $ui.Info.Text = (T "Se quitará NOVA AI de:`n{0}`n`nTambién sus accesos directos y su entrada en «Aplicaciones instaladas». Si conservas tus datos, al reinstalar NOVA lo recordará todo.") -f $Root
} else {
    $ui.Info.Text = (T "No encuentro NOVA AI en:`n{0}`n`nPuede que ya esté desinstalada. Puedes quitar igualmente los accesos directos y el registro.") -f $Root
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
        $ui.Status.Text = (T '✓ NOVA AI se ha desinstalado. ¡Buen vuelo, piloto!')
        if (-not $ui.ChkData.IsChecked) { $ui.Status.Text += (T "`n  Tus datos siguen en {0} por si vuelves.") -f $DataRoot }
    } else {
        $ui.Status.Text = (T "⚠ Algunos archivos estaban en uso y no se pudieron borrar.`n  Reinicia el PC y borra a mano la carpeta: {0}") -f $Root
        $ui.Status.Foreground = New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString('#E8C15A'))
    }
    $ui.BtnGo.Content = (T 'CERRAR'); $ui.BtnGo.IsEnabled = $true
    $script:finished = $true
})
$script:finished = $false
[void]$window.ShowDialog()
exit 0
