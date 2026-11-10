<#
  NOVA AI · Instalador gráfico holográfico
  Windows PowerShell 5.1 + WPF (incluidos en Windows 10/11). No necesita Python:
  si falta, lo descarga e instala para tu usuario.

  Instala el programa en «Archivos de programa\NOVA AI» (C:\Program Files\NOVA AI), crea los
  accesos directos y lo registra en «Aplicaciones instaladas» con su desinstalador.
  Tus datos (ajustes, comandos, memoria) viven aparte, en %LOCALAPPDATA%\NOVA AI\datos.
#>
param([string]$Destino = '', [string]$Origen = '', [switch]$Actualizar, [switch]$SinIniciar)
# -Actualizar: lo abre NOVA AI cuando hay una versión nueva en GitHub (empieza solo, sin preguntar de nuevo
#  las normas si ya estaban aceptadas). -SinIniciar: no volver a abrir NOVA al terminar (actualizar «al cerrar»).
$ErrorActionPreference = 'Continue'
$AppName = 'NOVA AI'
$AppVersion = '1.2.1'
# Origen: carpeta con el programa a instalar. «NOVA AI Setup.exe» la pasa (la descomprime en TEMP);
# con INSTALAR.bat es la carpeta padre de este script.
$Src = if ($Origen) { $Origen } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$ErrLog = Join-Path $env:TEMP 'NOVA_AI_Setup_error.log'

# Cualquier error grave que no esté controlado se explica en una ventana (antes la consola se cerraba sin decir nada).
function Show-Fatal([string]$msg) {
    try { [IO.File]::AppendAllText($ErrLog, ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) + [Environment]::NewLine) } catch {}
    Write-Output $msg
    if ($env:NOVA_SETUP_READY) { return }  # lo explica «NOVA AI Setup.exe» en su propia ventana
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(("El instalador de NOVA AI ha encontrado un problema:`n`n" + $msg +
            "`n`nDetalles guardados en:`n" + $ErrLog), 'NOVA AI · Instalación', 'OK', 'Error')
    } catch {}
}
trap {
    Show-Fatal ($_.Exception.Message + "`n" + $_.InvocationInfo.PositionMessage)
    exit 4
}
$Root = if ($Destino) { $Destino } else { Join-Path $env:ProgramFiles $AppName }
$UserData = Join-Path $env:LOCALAPPDATA 'NOVA AI\datos'

# Escribir en Archivos de programa exige permisos de administrador: se piden con la ventana de Windows (UAC).
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    try {
        if (-not $PSCommandPath) { throw 'sin ruta del script' }
        $argList = '-NoProfile -ExecutionPolicy Bypass -STA -File "' + $PSCommandPath + '" -Origen "' + $Src + '"'
        if ($Destino) { $argList += ' -Destino "' + $Destino + '"' }
        if ($Actualizar) { $argList += ' -Actualizar' }
        if ($SinIniciar) { $argList += ' -SinIniciar' }
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -ErrorAction Stop
        exit 0
    } catch {
        try {
            Add-Type -AssemblyName PresentationFramework
            [void][Windows.MessageBox]::Show(("Para instalar NOVA AI en «Archivos de programa» Windows pide permiso de administrador.`n`n" +
                "Vuelve a abrir «NOVA AI Setup» y pulsa «Sí» en la ventana de Windows."), 'NOVA AI', 'OK', 'Warning')
        } catch {}
        exit 3
    }
}
$PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
$OwnPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'

try {
    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml
} catch {
    Show-Fatal ('No se pudo cargar la parte gráfica de Windows (WPF): ' + $_.Exception.Message)
    exit 2
}

# =====================================================================  XAML
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="NOVA · Instalación" Width="1000" Height="660"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent"
        ResizeMode="NoResize" WindowStartupLocation="CenterScreen"
        FontFamily="Bahnschrift, Segoe UI" Foreground="#CFEFFF" UseLayoutRounding="True">
  <Window.Resources>
    <DropShadowEffect x:Key="Glow" Color="#20B8E8" BlurRadius="18" ShadowDepth="0" Opacity="0.95"/>
    <DropShadowEffect x:Key="GlowSoft" Color="#20B8E8" BlurRadius="10" ShadowDepth="0" Opacity="0.7"/>
    <DropShadowEffect x:Key="GlowText" Color="#20B8E8" BlurRadius="14" ShadowDepth="0" Opacity="0.8"/>

    <Style x:Key="HoloButton" TargetType="Button">
      <Setter Property="Foreground" Value="#DFF7FF"/>
      <Setter Property="FontSize" Value="15"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Padding" Value="28,11"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Grid>
              <Border x:Name="Bg" Background="#1A20B8E8" BorderBrush="#20B8E8" BorderThickness="1" CornerRadius="2"/>
              <Path Data="M0,9 L0,0 L9,0" Stroke="#8FE4FF" StrokeThickness="2" HorizontalAlignment="Left" VerticalAlignment="Top" Margin="-4,-4,0,0"/>
              <Path Data="M9,0 L9,9 L0,9" Stroke="#8FE4FF" StrokeThickness="2" HorizontalAlignment="Right" VerticalAlignment="Bottom" Margin="0,0,-4,-4"/>
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center" Margin="{TemplateBinding Padding}"/>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="Bg" Property="Background" Value="#3820B8E8"/>
                <Setter TargetName="Bg" Property="Effect" Value="{StaticResource Glow}"/>
              </Trigger>
              <Trigger Property="IsPressed" Value="True">
                <Setter TargetName="Bg" Property="Background" Value="#6020B8E8"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.35"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="FlatButton" TargetType="Button">
      <Setter Property="Foreground" Value="#7FA9C0"/>
      <Setter Property="FontSize" Value="14"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="Bg" Background="Transparent" Padding="10,4">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="Bg" Property="Background" Value="#2220B8E8"/>
                <Setter Property="Foreground" Value="#DFF7FF"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="HoloCheck" TargetType="CheckBox">
      <Setter Property="Foreground" Value="#CFEFFF"/>
      <Setter Property="FontSize" Value="14"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Margin" Value="0,7,0,7"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="CheckBox">
            <Grid Background="Transparent">
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="32"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <Grid Width="18" Height="18" VerticalAlignment="Top" HorizontalAlignment="Left" Margin="0,2,0,0">
                <Border BorderBrush="#20B8E8" BorderThickness="1" Background="#1020B8E8"/>
                <Path x:Name="Mark" Data="M9,2 L16,9 L9,16 L2,9 Z" Fill="#6FD8FF" Visibility="Collapsed" Effect="{StaticResource GlowSoft}"/>
              </Grid>
              <ContentPresenter Grid.Column="1" VerticalAlignment="Center"/>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="Mark" Property="Visibility" Value="Visible"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Opacity" Value="0.4"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="Caption" TargetType="TextBlock">
      <Setter Property="Foreground" Value="#20B8E8"/>
      <Setter Property="FontSize" Value="12"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Margin" Value="0,0,0,8"/>
    </Style>
    <Style x:Key="Dim" TargetType="TextBlock">
      <Setter Property="Foreground" Value="#6F93A8"/>
      <Setter Property="FontSize" Value="12"/>
      <Setter Property="TextWrapping" Value="Wrap"/>
    </Style>
  </Window.Resources>

  <Window.Triggers>
    <EventTrigger RoutedEvent="Window.Loaded">
      <BeginStoryboard>
        <Storyboard>
          <DoubleAnimation Storyboard.TargetName="RotA" Storyboard.TargetProperty="Angle" From="0" To="360" Duration="0:0:28" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="RotB" Storyboard.TargetProperty="Angle" From="360" To="0" Duration="0:0:17" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="RotC" Storyboard.TargetProperty="Angle" From="0" To="360" Duration="0:1:0" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="ScanT" Storyboard.TargetProperty="Y" From="-160" To="700" Duration="0:0:7" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="ShimmerT" Storyboard.TargetProperty="X" From="-220" To="1000" Duration="0:0:2.4" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="Beam" Storyboard.TargetProperty="Opacity" From="0.35" To="0.7" Duration="0:0:1.7" AutoReverse="True" RepeatBehavior="Forever"/>
          <DoubleAnimation Storyboard.TargetName="CoreDiamond" Storyboard.TargetProperty="Opacity" From="0.55" To="1" Duration="0:0:1.1" AutoReverse="True" RepeatBehavior="Forever"/>
          <DoubleAnimationUsingKeyFrames Storyboard.TargetName="Holo" Storyboard.TargetProperty="Opacity" Duration="0:0:5" RepeatBehavior="Forever">
            <DiscreteDoubleKeyFrame KeyTime="0:0:0" Value="1"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:2.10" Value="0.72"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:2.16" Value="1"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:2.30" Value="0.82"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:2.36" Value="1"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:4.40" Value="0.88"/>
            <DiscreteDoubleKeyFrame KeyTime="0:0:4.46" Value="1"/>
          </DoubleAnimationUsingKeyFrames>
        </Storyboard>
      </BeginStoryboard>
    </EventTrigger>
  </Window.Triggers>

  <Grid Margin="14">
    <!-- halo exterior (separado del contenido para no ralentizar las animaciones) -->
    <Border CornerRadius="6" Background="#060C16" BorderBrush="#6020B8E8" BorderThickness="1">
      <Border.Effect>
        <DropShadowEffect Color="#20B8E8" BlurRadius="26" ShadowDepth="0" Opacity="0.45"/>
      </Border.Effect>
    </Border>

    <Border CornerRadius="6" ClipToBounds="True">
      <Border.Background>
        <RadialGradientBrush Center="0.25,0.4" GradientOrigin="0.25,0.4" RadiusX="0.85" RadiusY="0.95">
          <GradientStop Color="#10263C" Offset="0"/>
          <GradientStop Color="#08111D" Offset="0.6"/>
          <GradientStop Color="#04080F" Offset="1"/>
        </RadialGradientBrush>
      </Border.Background>
      <Grid ClipToBounds="True">
        <!-- rejilla -->
        <Rectangle Opacity="0.07" IsHitTestVisible="False">
          <Rectangle.Fill>
            <DrawingBrush TileMode="Tile" Viewport="0,0,34,34" ViewportUnits="Absolute">
              <DrawingBrush.Drawing>
                <GeometryDrawing Geometry="M0,0 L34,0 M0,0 L0,34">
                  <GeometryDrawing.Pen>
                    <Pen Brush="#20B8E8" Thickness="1"/>
                  </GeometryDrawing.Pen>
                </GeometryDrawing>
              </DrawingBrush.Drawing>
            </DrawingBrush>
          </Rectangle.Fill>
        </Rectangle>
        <!-- líneas de barrido -->
        <Rectangle Opacity="0.05" IsHitTestVisible="False">
          <Rectangle.Fill>
            <DrawingBrush TileMode="Tile" Viewport="0,0,4,4" ViewportUnits="Absolute">
              <DrawingBrush.Drawing>
                <GeometryDrawing Geometry="M0,0 L4,0">
                  <GeometryDrawing.Pen>
                    <Pen Brush="#9FE8FF" Thickness="1"/>
                  </GeometryDrawing.Pen>
                </GeometryDrawing>
              </DrawingBrush.Drawing>
            </DrawingBrush>
          </Rectangle.Fill>
        </Rectangle>
        <Rectangle Height="160" VerticalAlignment="Top" IsHitTestVisible="False">
          <Rectangle.RenderTransform>
            <TranslateTransform x:Name="ScanT" Y="-160"/>
          </Rectangle.RenderTransform>
          <Rectangle.Fill>
            <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
              <GradientStop Color="#0020B8E8" Offset="0"/>
              <GradientStop Color="#1420B8E8" Offset="0.85"/>
              <GradientStop Color="#3020B8E8" Offset="0.98"/>
              <GradientStop Color="#0020B8E8" Offset="1"/>
            </LinearGradientBrush>
          </Rectangle.Fill>
        </Rectangle>

        <Grid>
          <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
          </Grid.RowDefinitions>

          <!-- ============ CABECERA ============ -->
          <Grid x:Name="Header" Grid.Row="0" Margin="30,18,14,0" Background="Transparent">
            <StackPanel Orientation="Horizontal">
              <Image x:Name="Logo" Width="46" Height="46" Margin="0,0,14,0"/>
              <StackPanel>
                <TextBlock Text="NOVA" FontSize="32" FontWeight="Bold" Foreground="#8FE4FF" Effect="{StaticResource GlowText}"/>
                <TextBlock x:Name="Subtitle" Text="" FontSize="12" Foreground="#20B8E8" Margin="2,0,0,0"/>
              </StackPanel>
            </StackPanel>
            <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Top">
              <TextBlock x:Name="Clock" FontFamily="Consolas" FontSize="11" Foreground="#4F7A92" VerticalAlignment="Center" Margin="0,0,14,0"/>
              <Button x:Name="BtnMin" Style="{StaticResource FlatButton}" Content="—"/>
              <Button x:Name="BtnClose" Style="{StaticResource FlatButton}" Content="✕"/>
            </StackPanel>
            <Rectangle Height="1" VerticalAlignment="Bottom" Margin="0,0,16,-10">
              <Rectangle.Fill>
                <LinearGradientBrush StartPoint="0,0" EndPoint="1,0">
                  <GradientStop Color="#0020B8E8" Offset="0"/>
                  <GradientStop Color="#AA20B8E8" Offset="0.3"/>
                  <GradientStop Color="#3320B8E8" Offset="0.8"/>
                  <GradientStop Color="#0020B8E8" Offset="1"/>
                </LinearGradientBrush>
              </Rectangle.Fill>
            </Rectangle>
          </Grid>

          <!-- ============ CUERPO ============ -->
          <Grid Grid.Row="1" Margin="22,22,30,8">
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="350"/>
              <ColumnDefinition Width="*"/>
            </Grid.ColumnDefinitions>

            <!-- Holograma -->
            <Grid Grid.Column="0" VerticalAlignment="Center">
              <Grid.RowDefinitions>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
              </Grid.RowDefinitions>
              <!-- haz del proyector -->
              <Path x:Name="Beam" Grid.Row="0" Data="M150,330 L30,40 L270,40 Z" Width="300" Height="330" Opacity="0.5" HorizontalAlignment="Center" VerticalAlignment="Top" IsHitTestVisible="False">
                <Path.Fill>
                  <LinearGradientBrush StartPoint="0,1" EndPoint="0,0">
                    <GradientStop Color="#5520B8E8" Offset="0"/>
                    <GradientStop Color="#0020B8E8" Offset="0.9"/>
                  </LinearGradientBrush>
                </Path.Fill>
              </Path>
              <Grid x:Name="Holo" Grid.Row="0" Width="300" Height="300">
                <Ellipse Width="292" Height="292" Stroke="#3320B8E8" StrokeThickness="1"/>
                <Ellipse Width="276" Height="276" Stroke="#20B8E8" StrokeThickness="3" StrokeDashArray="1 5" Opacity="0.65" RenderTransformOrigin="0.5,0.5">
                  <Ellipse.RenderTransform>
                    <RotateTransform x:Name="RotA"/>
                  </Ellipse.RenderTransform>
                </Ellipse>
                <Canvas x:Name="Ticks" Width="300" Height="300" RenderTransformOrigin="0.5,0.5" Opacity="0.75">
                  <Canvas.RenderTransform>
                    <RotateTransform x:Name="RotC"/>
                  </Canvas.RenderTransform>
                </Canvas>
                <Ellipse Width="236" Height="236" Stroke="#6FD8FF" StrokeThickness="1.5" StrokeDashArray="18 6 3 6" Opacity="0.45" RenderTransformOrigin="0.5,0.5">
                  <Ellipse.RenderTransform>
                    <RotateTransform x:Name="RotB"/>
                  </Ellipse.RenderTransform>
                </Ellipse>
                <Ellipse Width="200" Height="200" Stroke="#1E20B8E8" StrokeThickness="9"/>
                <Path x:Name="Arc" Stroke="#6FD8FF" StrokeThickness="9" StrokeStartLineCap="Round" StrokeEndLineCap="Round"
                      HorizontalAlignment="Left" VerticalAlignment="Top" Effect="{StaticResource Glow}"/>
                <Ellipse Width="168" Height="168">
                  <Ellipse.Fill>
                    <RadialGradientBrush>
                      <GradientStop Color="#2020B8E8" Offset="0"/>
                      <GradientStop Color="#0020B8E8" Offset="1"/>
                    </RadialGradientBrush>
                  </Ellipse.Fill>
                </Ellipse>
                <Path x:Name="CoreDiamond" Data="M150,96 L160,108 L150,120 L140,108 Z" Fill="#6FD8FF" HorizontalAlignment="Left" VerticalAlignment="Top" Effect="{StaticResource GlowSoft}"/>
                <StackPanel VerticalAlignment="Center" HorizontalAlignment="Center" Margin="0,22,0,0">
                  <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                    <TextBlock x:Name="Pct" Text="0" FontSize="58" FontWeight="Bold" Foreground="#DFF7FF" Effect="{StaticResource GlowText}"/>
                    <TextBlock Text="%" FontSize="24" Foreground="#20B8E8" Margin="3,0,0,12" VerticalAlignment="Bottom"/>
                  </StackPanel>
                  <TextBlock x:Name="EtaSmall" Text="EN ESPERA" FontFamily="Consolas" FontSize="12" Foreground="#6FD8FF" HorizontalAlignment="Center"/>
                </StackPanel>
              </Grid>
              <!-- base del proyector -->
              <Grid Grid.Row="1" Margin="0,16,0,0">
                <Ellipse Width="230" Height="26" Stroke="#6620B8E8" StrokeThickness="1">
                  <Ellipse.Fill>
                    <RadialGradientBrush>
                      <GradientStop Color="#5520B8E8" Offset="0"/>
                      <GradientStop Color="#0020B8E8" Offset="1"/>
                    </RadialGradientBrush>
                  </Ellipse.Fill>
                </Ellipse>
                <Ellipse Width="150" Height="14" Stroke="#AA6FD8FF" StrokeThickness="1"/>
              </Grid>
            </Grid>

            <!-- Paneles de la derecha -->
            <Grid Grid.Column="1" Margin="28,0,0,0">

              <!-- 0) Normas de uso y privacidad: hay que aceptarlas antes de instalar -->
              <Grid x:Name="PanelTerms" Visibility="Visible">
                <Grid.RowDefinitions>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="*"/>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="Auto"/>
                </Grid.RowDefinitions>
                <TextBlock Style="{StaticResource Caption}" Text="▸ NORMAS DE USO Y POLÍTICA DE PRIVACIDAD"/>
                <TextBlock Grid.Row="1" Style="{StaticResource Dim}" FontSize="13" Foreground="#8FB8CC" Margin="0,0,0,10"
                           Text="Antes de instalar, lee y acepta cómo funciona NOVA AI con tus datos. Resumen: todo se queda en tu PC, no se hacen grabaciones y las consultas a internet son las mismas que harías tú en Google o en una IA."/>
                <Border Grid.Row="2" BorderBrush="#2A20B8E8" BorderThickness="1" Background="#0A20B8E8">
                  <ScrollViewer x:Name="TermsScroll" VerticalScrollBarVisibility="Auto" Padding="14,10">
                    <StackPanel x:Name="TermsBody"/>
                  </ScrollViewer>
                </Border>
                <CheckBox x:Name="ChkTerms" Grid.Row="3" Style="{StaticResource HoloCheck}" Margin="0,12,0,10">
                  <TextBlock Text="He leído y acepto las Normas de uso y la Política de privacidad" TextWrapping="Wrap"/>
                </CheckBox>
                <StackPanel Grid.Row="4" Orientation="Horizontal">
                  <Button x:Name="BtnAccept" Style="{StaticResource HoloButton}" IsEnabled="False" Margin="0,0,18,0">
                    <TextBlock Text="◆  ACEPTAR Y CONTINUAR" FontWeight="SemiBold"/>
                  </Button>
                  <Button x:Name="BtnDecline" Style="{StaticResource FlatButton}" Content="NO ACEPTO · SALIR"/>
                </StackPanel>
              </Grid>

              <!-- 1) Diagnóstico y opciones -->
              <StackPanel x:Name="PanelOptions" Visibility="Collapsed">
                <TextBlock Style="{StaticResource Caption}" Text="▸ DIAGNÓSTICO DEL SISTEMA"/>
                <Border BorderBrush="#2A20B8E8" BorderThickness="1" Background="#0A20B8E8" Padding="14,10" Margin="0,0,0,16">
                  <StackPanel>
                    <TextBlock x:Name="DiagPython" Text="◇  Python ··· analizando" Margin="0,2"/>
                    <TextBlock x:Name="DiagGpu" Text="◇  Tarjeta gráfica ··· analizando" Margin="0,2"/>
                    <TextBlock x:Name="DiagDisk" Text="◇  Espacio en disco ··· analizando" Margin="0,2"/>
                    <TextBlock x:Name="DiagNet" Text="◇  Conexión ··· analizando" Margin="0,2"/>
                    <DockPanel Margin="0,2">
                      <Button x:Name="BtnPath" DockPanel.Dock="Right" Style="{StaticResource FlatButton}" FontSize="11" Content="CAMBIAR…" Margin="8,0,0,0"/>
                      <TextBlock x:Name="DiagPath" Text="◇  Destino ···" TextTrimming="CharacterEllipsis" VerticalAlignment="Center"/>
                    </DockPanel>
                  </StackPanel>
                </Border>
                <TextBlock Style="{StaticResource Caption}" Text="▸ MÓDULOS A INSTALAR"/>
                <CheckBox x:Name="ChkCuda" Style="{StaticResource HoloCheck}">
                  <StackPanel>
                    <TextBlock Text="Aceleración NVIDIA CUDA para el reconocimiento de voz"/>
                    <TextBlock x:Name="ChkCudaSub" Style="{StaticResource Dim}" Text="Whisper local mucho más rápido · descarga ≈ 1 GB"/>
                  </StackPanel>
                </CheckBox>
                <CheckBox x:Name="ChkPiper" Style="{StaticResource HoloCheck}" IsChecked="True">
                  <StackPanel>
                    <TextBlock Text="Voz sin internet (Piper)"/>
                    <TextBlock Style="{StaticResource Dim}" Text="Respaldo si no hay conexión · ≈ 25 MB"/>
                  </StackPanel>
                </CheckBox>
                <CheckBox x:Name="ChkShortcut" Style="{StaticResource HoloCheck}" IsChecked="True">
                  <StackPanel>
                    <TextBlock Text="Acceso directo en el escritorio y en el menú Inicio"/>
                  </StackPanel>
                </CheckBox>
                <CheckBox x:Name="ChkLaunch" Style="{StaticResource HoloCheck}" IsChecked="True">
                  <StackPanel>
                    <TextBlock Text="Iniciar Nova al terminar"/>
                  </StackPanel>
                </CheckBox>
                <TextBlock x:Name="EstimateText" Style="{StaticResource Dim}" Margin="0,14,0,16" FontSize="13" Foreground="#8FB8CC"/>
                <Button x:Name="BtnStart" Style="{StaticResource HoloButton}" HorizontalAlignment="Left" IsEnabled="False">
                  <TextBlock Text="◆  INICIAR SECUENCIA DE INSTALACIÓN" FontWeight="SemiBold"/>
                </Button>
              </StackPanel>

              <!-- 2) Secuencia en curso -->
              <Grid x:Name="PanelSteps" Visibility="Collapsed">
                <Grid.RowDefinitions>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="Auto"/>
                  <RowDefinition Height="*"/>
                </Grid.RowDefinitions>
                <TextBlock Grid.Row="0" Style="{StaticResource Caption}" Text="▸ SECUENCIA DE INSTALACIÓN"/>
                <StackPanel Grid.Row="1" x:Name="StepsList"/>
                <StackPanel Grid.Row="2" Margin="0,12,0,8">
                  <TextBlock x:Name="StatusText" FontSize="16" Foreground="#DFF7FF" TextTrimming="CharacterEllipsis"/>
                  <TextBlock x:Name="DetailText" FontFamily="Consolas" FontSize="12" Foreground="#6FD8FF" Margin="0,3,0,0" TextTrimming="CharacterEllipsis"/>
                </StackPanel>
                <Grid Grid.Row="3">
                  <Grid.RowDefinitions>
                    <RowDefinition Height="Auto"/>
                    <RowDefinition Height="*"/>
                  </Grid.RowDefinitions>
                  <Button x:Name="BtnLogToggle" Style="{StaticResource FlatButton}" HorizontalAlignment="Left" FontSize="11" Content="▸ REGISTRO TÉCNICO"/>
                  <Border x:Name="LogBorder" Grid.Row="1" BorderBrush="#2220B8E8" BorderThickness="1" Background="#A0000307" Visibility="Collapsed" Margin="0,4,0,0">
                    <TextBox x:Name="LogBox" IsReadOnly="True" Background="Transparent" BorderThickness="0" Foreground="#5FC8EE"
                             FontFamily="Consolas" FontSize="11" TextWrapping="NoWrap" VerticalScrollBarVisibility="Auto"
                             HorizontalScrollBarVisibility="Auto" Padding="6"/>
                  </Border>
                </Grid>
              </Grid>

              <!-- 3) Final -->
              <StackPanel x:Name="PanelDone" Visibility="Collapsed" VerticalAlignment="Center">
                <TextBlock Text="◆ INSTALACIÓN COMPLETADA" FontSize="28" FontWeight="Bold" Foreground="#8FE4FF" Effect="{StaticResource GlowText}"/>
                <TextBlock x:Name="DoneText" FontSize="15" Foreground="#CFEFFF" TextWrapping="Wrap" Margin="0,12,0,8"/>
                <TextBlock x:Name="DoneWarn" Style="{StaticResource Dim}" Foreground="#E8C15A" Margin="0,0,0,20"/>
                <StackPanel Orientation="Horizontal">
                  <Button x:Name="BtnLaunch" Style="{StaticResource HoloButton}" Margin="0,0,18,0">
                    <TextBlock Text="▶  LANZAR NOVA" FontWeight="SemiBold"/>
                  </Button>
                  <Button x:Name="BtnFinish" Style="{StaticResource HoloButton}">
                    <TextBlock Text="CERRAR"/>
                  </Button>
                </StackPanel>
              </StackPanel>

              <!-- 4) Error -->
              <StackPanel x:Name="PanelError" Visibility="Collapsed" VerticalAlignment="Center">
                <TextBlock Text="⚠ FALLO EN LA SECUENCIA" FontSize="26" FontWeight="Bold" Foreground="#FF6B7A">
                  <TextBlock.Effect>
                    <DropShadowEffect Color="#FF3B4E" BlurRadius="14" ShadowDepth="0" Opacity="0.8"/>
                  </TextBlock.Effect>
                </TextBlock>
                <TextBlock x:Name="ErrorText" FontSize="14" Foreground="#FFC7CD" TextWrapping="Wrap" Margin="0,12,0,8"/>
                <TextBlock x:Name="ErrorTail" FontFamily="Consolas" FontSize="11" Foreground="#C08A92" TextWrapping="Wrap" Margin="0,0,0,18"/>
                <StackPanel Orientation="Horizontal">
                  <Button x:Name="BtnRetry" Style="{StaticResource HoloButton}" Margin="0,0,18,0">
                    <TextBlock Text="↻  REINTENTAR"/>
                  </Button>
                  <Button x:Name="BtnOpenLog" Style="{StaticResource HoloButton}">
                    <TextBlock Text="VER REGISTRO"/>
                  </Button>
                </StackPanel>
              </StackPanel>
            </Grid>
          </Grid>

          <!-- ============ PIE: barra y tiempos ============ -->
          <StackPanel Grid.Row="2" Margin="30,4,30,22">
            <Grid x:Name="BarTrack" Height="12" ClipToBounds="True">
              <Border Background="#1220B8E8" BorderBrush="#4020B8E8" BorderThickness="1"/>
              <Border x:Name="BarFill" HorizontalAlignment="Left" Width="0" Effect="{StaticResource Glow}">
                <Border.Background>
                  <LinearGradientBrush StartPoint="0,0" EndPoint="1,0">
                    <GradientStop Color="#1478A8" Offset="0"/>
                    <GradientStop Color="#20B8E8" Offset="0.7"/>
                    <GradientStop Color="#9FEBFF" Offset="1"/>
                  </LinearGradientBrush>
                </Border.Background>
                <Grid ClipToBounds="True">
                  <Rectangle Width="160" HorizontalAlignment="Left" IsHitTestVisible="False">
                    <Rectangle.RenderTransform>
                      <TranslateTransform x:Name="ShimmerT" X="-220"/>
                    </Rectangle.RenderTransform>
                    <Rectangle.Fill>
                      <LinearGradientBrush StartPoint="0,0" EndPoint="1,0">
                        <GradientStop Color="#00FFFFFF" Offset="0"/>
                        <GradientStop Color="#55FFFFFF" Offset="0.5"/>
                        <GradientStop Color="#00FFFFFF" Offset="1"/>
                      </LinearGradientBrush>
                    </Rectangle.Fill>
                  </Rectangle>
                </Grid>
              </Border>
              <Rectangle IsHitTestVisible="False" Opacity="0.55">
                <Rectangle.Fill>
                  <DrawingBrush TileMode="Tile" Viewport="0,0,10,12" ViewportUnits="Absolute">
                    <DrawingBrush.Drawing>
                      <GeometryDrawing Geometry="M9,0 L9,12">
                        <GeometryDrawing.Pen>
                          <Pen Brush="#04080F" Thickness="2"/>
                        </GeometryDrawing.Pen>
                      </GeometryDrawing>
                    </DrawingBrush.Drawing>
                  </DrawingBrush>
                </Rectangle.Fill>
              </Rectangle>
            </Grid>
            <Grid Margin="0,9,0,0">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="TRANSCURRIDO " FontSize="11" Foreground="#4F7A92"/>
                <TextBlock x:Name="Elapsed" Text="00:00" FontFamily="Consolas" FontSize="12" Foreground="#9FD8F0" Margin="0,0,26,0"/>
                <TextBlock Text="TIEMPO RESTANTE " FontSize="11" Foreground="#4F7A92"/>
                <TextBlock x:Name="Remaining" Text="—" FontFamily="Consolas" FontSize="12" Foreground="#DFF7FF" Margin="0,0,26,0"/>
                <TextBlock Text="VELOCIDAD " FontSize="11" Foreground="#4F7A92"/>
                <TextBlock x:Name="Speed" Text="—" FontFamily="Consolas" FontSize="12" Foreground="#9FD8F0"/>
              </StackPanel>
              <TextBlock x:Name="PctFooter" HorizontalAlignment="Right" Text="0 %" FontFamily="Consolas" FontSize="13" Foreground="#6FD8FF"/>
            </Grid>
          </StackPanel>
        </Grid>
      </Grid>
    </Border>
  </Grid>
</Window>
'@

# ==================================================================  VENTANA
try {
    $window = [Windows.Markup.XamlReader]::Parse($xaml)
} catch {
    Show-Fatal ('No se pudo crear la ventana del instalador: ' + $_.Exception.Message)
    exit 2
}

# Oculta la consola negra ahora que la ventana existe.
try {
    Add-Type -Namespace NovaInstaller -Name Native -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern System.IntPtr GetConsoleWindow();
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
'@
    [void][NovaInstaller.Native]::ShowWindow([NovaInstaller.Native]::GetConsoleWindow(), 0)
} catch {}

$ui = @{}
foreach ($n in 'Header','Logo','Subtitle','Clock','BtnMin','BtnClose','Ticks','Arc','Pct','EtaSmall',
               'PanelOptions','DiagPython','DiagGpu','DiagDisk','DiagNet','DiagPath','BtnPath','ChkCuda','ChkCudaSub','ChkPiper',
               'ChkShortcut','ChkLaunch','EstimateText','BtnStart','PanelSteps','StepsList','StatusText',
               'DetailText','BtnLogToggle','LogBorder','LogBox','PanelDone','DoneText','DoneWarn','BtnLaunch',
               'BtnFinish','PanelError','ErrorText','ErrorTail','BtnRetry','BtnOpenLog','BarTrack','BarFill',
               'Elapsed','Remaining','Speed','PctFooter','PanelTerms','TermsScroll','TermsBody','ChkTerms','BtnAccept','BtnDecline') {
    $ui[$n] = $window.FindName($n)
}

$iconPath = Join-Path $Src 'recursos\nova.ico'
$pngPath = Join-Path $Src 'recursos\nova.png'
function Show-Destination { $ui.DiagPath.Text = '◇  Destino ··· ' + $script:Root }
$script:Root = $Root
try {
    if (Test-Path $iconPath) { $window.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri]$iconPath) }
    if (Test-Path $pngPath) { $ui.Logo.Source = [Windows.Media.Imaging.BitmapFrame]::Create([Uri]$pngPath) }
} catch {}

# Marcas del holograma (72 rayitas, una de cada 6 más larga)
$tickBrush = New-Object Windows.Media.SolidColorBrush ([Windows.Media.Color]::FromRgb(0x6F, 0xD8, 0xFF))
for ($i = 0; $i -lt 72; $i++) {
    $a = $i / 72.0 * 2 * [Math]::PI
    $r1 = 124.0
    $r2 = if ($i % 6 -eq 0) { 135.0 } else { 130.0 }
    $line = New-Object Windows.Shapes.Line
    $line.X1 = 150 + $r1 * [Math]::Sin($a); $line.Y1 = 150 - $r1 * [Math]::Cos($a)
    $line.X2 = 150 + $r2 * [Math]::Sin($a); $line.Y2 = 150 - $r2 * [Math]::Cos($a)
    $line.Stroke = $tickBrush
    $line.StrokeThickness = if ($i % 6 -eq 0) { 2 } else { 1 }
    [void]$ui.Ticks.Children.Add($line)
}

$Inv = [Globalization.CultureInfo]::InvariantCulture
function Set-Arc([double]$p) {
    $p = [Math]::Max(0.001, [Math]::Min($p, 0.9999))
    $a = $p * 2 * [Math]::PI
    $x = 150 + 100 * [Math]::Sin($a)
    $y = 150 - 100 * [Math]::Cos($a)
    $large = if ($p -gt 0.5) { 1 } else { 0 }
    $d = [string]::Format($Inv, 'M 150,50 A 100,100 0 {0} 1 {1:0.###},{2:0.###}', $large, $x, $y)
    $ui.Arc.Data = [Windows.Media.Geometry]::Parse($d)
}
Set-Arc 0

function Format-Duration([double]$s) {
    $s = [Math]::Max(0, [Math]::Round($s))
    $m = [Math]::Floor($s / 60)
    $sec = $s % 60
    if ($m -ge 60) { return ('{0} h {1:00} min' -f [Math]::Floor($m / 60), ($m % 60)) }
    if ($m -ge 1) { return ('{0} min {1:00} s' -f $m, $sec) }
    return ('{0} s' -f $sec)
}
function Format-Clock([double]$s) {
    $s = [Math]::Max(0, [Math]::Round($s))
    return ('{0:00}:{1:00}' -f [Math]::Floor($s / 60), ($s % 60))
}
function Set-Color($el, [string]$hex) {
    $el.Foreground = New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString($hex))
}

# ======================================================  ESTADO COMPARTIDO
$sync = [hashtable]::Synchronized(@{
    Log = New-Object 'System.Collections.Concurrent.ConcurrentQueue[string]'
    StepIndex = -1; StepFrac = 0.0; StepStart = [DateTime]::Now; Creep = $true
    Status = ''; Detail = ''; Speed = 0.0
    Done = $false; Failed = $false; Error = ''; Warn = ''; Cancel = $false; ChildPid = 0
    Diag = $null; DiagDone = $false; States = $null; RawProgress = $false; PythonExe = ''
})
$script:runspaces = @()

function Start-Background([scriptblock]$code, [object[]]$arguments) {
    $rs = [runspacefactory]::CreateRunspace([initialsessionstate]::CreateDefault())
    $rs.ApartmentState = 'STA'
    $rs.ThreadOptions = 'ReuseThread'
    $rs.Open()
    $ps = [powershell]::Create()
    $ps.Runspace = $rs
    [void]$ps.AddScript($code)
    foreach ($a in $arguments) { [void]$ps.AddArgument($a) }
    $script:runspaces += , @($ps, $ps.BeginInvoke())
}

# ==========================================================  DIAGNÓSTICO
$detect = {
    param($sync, $Root, $OwnPython)
    $ErrorActionPreference = 'Continue'
    $r = @{ PyExe = ''; PyVer = ''; OtherVer = ''; Gpu = ''; Nvidia = $false; FreeGB = -1; Net = $false; Repair = $false }
    $code = "import sys,struct;print(sys.executable);print('%d.%d.%d' % sys.version_info[:3]);print(struct.calcsize('P')*8)"
    $cands = @(@('py', '-3.12'), @('py', '-3.11'), @('py', '-3.13'), @($OwnPython, ''), @('python', ''))
    foreach ($c in $cands) {
        try {
            if ($c[0] -like '*\*') { if (-not (Test-Path $c[0])) { continue } }
            elseif (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
            $argv = @()
            if ($c[1]) { $argv += $c[1] }
            $argv += @('-c', $code)
            $out = @(& $c[0] @argv 2>$null)
            if ($LASTEXITCODE -eq 0 -and $out.Count -ge 3) {
                $v = [version]$out[1].Trim()
                if ($v.Major -eq 3 -and $v.Minor -ge 11 -and $v.Minor -le 13 -and $out[2].Trim() -eq '64') {
                    $r.PyExe = $out[0].Trim(); $r.PyVer = $out[1].Trim(); break
                } elseif (-not $r.OtherVer) {
                    $r.OtherVer = $out[1].Trim()
                }
            }
        } catch {}
    }
    try {
        $gpus = @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object { $_.Name })
        $nv = @($gpus | Where-Object { $_ -match 'NVIDIA' })
        if ($nv.Count -gt 0) { $r.Gpu = $nv[0]; $r.Nvidia = $true } elseif ($gpus.Count -gt 0) { $r.Gpu = $gpus[0] }
    } catch {}
    try {
        $drive = Get-PSDrive -Name $Root.Substring(0, 1) -ErrorAction Stop
        $r.FreeGB = [Math]::Round($drive.Free / 1GB, 1)
    } catch {}
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
        $req = [Net.HttpWebRequest]::Create('https://pypi.org/simple/pip/')
        $req.Method = 'HEAD'; $req.Timeout = 6000
        $resp = $req.GetResponse(); $resp.Close(); $r.Net = $true
    } catch {}
    $okVer = 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)'
    $venvPy = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path (Join-Path $Root 'instalado.json')) { $r.Repair = $true }
    if (Test-Path $venvPy) {
        try { & $venvPy -c $okVer 2>$null; if ($LASTEXITCODE -eq 0) { $r.Repair = $true } } catch {}
    }
    $sync.Diag = $r
    $sync.DiagDone = $true
}

# ==========================================================  INSTALACIÓN
$worker = {
    param($sync, $plan, $Root, $opts)
    $ErrorActionPreference = 'Continue'
    $Src = $opts.Src
    $UserData = $opts.UserData
    try { [void](New-Item -ItemType Directory -Force -Path $UserData) } catch {}
    $logFile = Join-Path $UserData 'instalacion.log'
    $venvPy = Join-Path $Root '.venv\Scripts\python.exe'
    $Inv = [Globalization.CultureInfo]::InvariantCulture

    function Write-Log([string]$m) {
        $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
        $sync.Log.Enqueue($line)
        try { [IO.File]::AppendAllText($logFile, $line + [Environment]::NewLine, [Text.Encoding]::UTF8) } catch {}
    }
    function Set-Frac([double]$f) {
        $f = [Math]::Min(1.0, $f)
        if ($f -gt $sync.StepFrac) { $sync.StepFrac = $f }
    }

    function Get-File([string]$url, [string]$dest) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
        $req = [Net.HttpWebRequest]::Create($url)
        $req.UserAgent = 'NovaInstaller/1.0'
        $resp = $req.GetResponse()
        $total = [double]$resp.ContentLength
        $in = $resp.GetResponseStream()
        $out = [IO.File]::Create($dest)
        $buf = New-Object byte[] 262144
        $done = 0.0
        $sw = [Diagnostics.Stopwatch]::StartNew()
        try {
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
                if ($sync.Cancel) { throw 'Instalación cancelada' }
                $out.Write($buf, 0, $n)
                $done += $n
                $sync.Speed = ($done / 1MB) / [Math]::Max($sw.Elapsed.TotalSeconds, 0.1)
                if ($total -gt 0) {
                    Set-Frac ($done / $total)
                    $sync.Detail = '{0:N1} / {1:N1} MB' -f ($done / 1MB), ($total / 1MB)
                }
            }
        } finally {
            $out.Close(); $in.Close(); $resp.Close()
        }
        $sync.Speed = 0
    }

    function Invoke-Proc([string]$exe, [string]$arguments, [scriptblock]$onLine) {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = $arguments
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
        $psi.WorkingDirectory = $(if (Test-Path $Root) { $Root } else { $Src })
        $psi.EnvironmentVariables['PYTHONUNBUFFERED'] = '1'
        $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        $psi.EnvironmentVariables['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
        $p = [Diagnostics.Process]::Start($psi)
        $sync.ChildPid = $p.Id
        $errTask = $p.StandardError.ReadToEndAsync()
        while ($null -ne ($line = $p.StandardOutput.ReadLine())) {
            if ($line.Trim().Length -gt 0) {
                if ($line -notmatch '^Progress \d+ of \d+') { Write-Log $line }
                if ($onLine) { & $onLine $line }
            }
            if ($sync.Cancel) { try { $p.Kill() } catch {}; break }
        }
        $p.WaitForExit()
        $err = $errTask.Result
        if ($err) { foreach ($l in ($err -split "`r?`n")) { if ($l.Trim()) { Write-Log $l } } }
        $sync.ChildPid = 0
        if ($sync.Cancel) { throw 'Instalación cancelada' }
        return $p.ExitCode
    }

    # --- lectura de la salida de pip para el progreso ---
    $pst = @{ Done = 0.0; Cur = 0.0; CurTotal = 0.0; Expected = 1.0; Start = [DateTime]::Now; Lines = @(); PipVer = ''; Fails = (New-Object System.Collections.ArrayList) }
    $pipLine = {
        param($l)
        $pst.Lines = @((@($pst.Lines) + @($l)) | Select-Object -Last 12)
        if ($l -match '^Collecting (\S+)') {
            $sync.Detail = 'Analizando ' + ($Matches[1] -replace '[<>=!~;\[].*$', '')
        } elseif ($l -match '(Downloading|Using cached)\s+(\S+)\s+\(([\d\.,]+)\s*(kB|MB|GB)\)') {
            $file = ($Matches[2] -split '/')[-1]
            $name = ($file -split '-')[0]
            if ($file -like '*.metadata') { $sync.Detail = 'Analizando ' + $name; return }
            $mult = switch ($Matches[4]) { 'kB' { 1KB } 'MB' { 1MB } default { 1GB } }
            $size = [double]::Parse(($Matches[3] -replace ',', ''), $Inv) * $mult
            $pst.Done += [Math]::Max($pst.Cur, $pst.CurTotal)
            $pst.Cur = 0.0
            $pst.CurTotal = $size
            if ($Matches[1] -eq 'Downloading') {
                $sync.Detail = 'Descargando {0} ({1:N1} MB)' -f $name, ($size / 1MB)
            } else {
                $sync.Detail = 'Desde caché: {0}' -f $name
                $pst.Cur = $size
            }
            Set-Frac (0.85 * ($pst.Done + $pst.Cur) / $pst.Expected)
        } elseif ($l -match '^Progress (\d+) of (\d+)') {
            $pst.Cur = [double]$Matches[1]
            $tot = [double]$Matches[2]
            if ($tot -gt 0) { $pst.CurTotal = $tot }
            $bytes = $pst.Done + $pst.Cur
            $sync.Speed = ($bytes / 1MB) / [Math]::Max(([DateTime]::Now - $pst.Start).TotalSeconds, 0.1)
            Set-Frac (0.85 * $bytes / $pst.Expected)
            if ($pst.CurTotal -gt 0) {
                $sync.Detail = ($sync.Detail -replace ' · .*$', '') + (' · {0:N1} / {1:N1} MB' -f ($pst.Cur / 1MB), ($pst.CurTotal / 1MB))
            }
        } elseif ($l -match '^Installing collected packages') {
            Set-Frac 0.86
            $sync.Speed = 0
            $sync.Detail = 'Integrando paquetes en el entorno…'
        } elseif ($l -match '^Successfully installed') {
            Set-Frac 1.0
        } elseif ($l -match '^Requirement already satisfied: (\S+)') {
            $sync.Detail = 'Ya instalado: ' + $Matches[1]
        }
    }

    function Install-Pkgs([string[]]$pkgs, [double]$mb) {
        $pst.Done = 0.0; $pst.Cur = 0.0; $pst.CurTotal = 0.0
        $pst.Expected = [Math]::Max($mb, 1.0) * 1MB
        $pst.Start = [DateTime]::Now
        $quoted = ($pkgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
        $bar = if ($sync.RawProgress) { '--progress-bar raw ' } else { '' }
        $bin = '--prefer-binary --only-binary=numpy,pillow,pygame,ctranslate2,onnxruntime,av,tokenizers,rapidfuzz,miniaudio,sounddevice '
        $code = Invoke-Proc $venvPy ("-m pip install --no-input --upgrade-strategy only-if-needed $bin$bar$quoted") $pipLine
        if ($code -ne 0) {
            $tail = ($pst.Lines | Select-Object -Last 4) -join ' | '
            throw "pip terminó con error ($code). $tail"
        }
    }

    Write-Log "===== Instalación de NOVA AI $($opts.Version) · $(Get-Date -Format 'yyyy-MM-dd HH:mm') ====="
    Write-Log "Origen: $Src"
    Write-Log "Destino: $Root"
    Write-Log "Tus datos: $UserData"

    $py = $opts.PyExe
    for ($i = 0; $i -lt $plan.Count; $i++) {
        $s = $plan[$i]
        $sync.StepIndex = $i
        $sync.StepFrac = 0.0
        $sync.StepStart = [DateTime]::Now
        $sync.Creep = $true
        $sync.Speed = 0.0
        $sync.Detail = ''
        $sync.Status = $s.Name
        $sync.States[$i] = 'active'
        Write-Log ('>>> ' + $s.Name)
        try {
            switch ($s.Id) {
                'prep' {
                    # 1) Cerrar Nova si está abierta (sus archivos se van a sustituir)
                    $sync.Detail = 'Cerrando NOVA si está abierta…'
                    try {
                        Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                            ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) -or
                            ($_.CommandLine -and $_.CommandLine -like '*NOVA AI\datos\interfaz*')
                        } | ForEach-Object { Write-Log "Cerrando $($_.Name) ($($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
                    } catch {}
                    Set-Frac 0.1
                    # 2) Copiar el programa a Archivos de programa
                    $same = $false
                    try { $same = ([IO.Path]::GetFullPath($Src).TrimEnd('\') -ieq [IO.Path]::GetFullPath($Root).TrimEnd('\')) } catch {}
                    if ($same) {
                        Write-Log 'Instalando desde la propia carpeta de destino: no hace falta copiar'
                    } else {
                        [void](New-Item -ItemType Directory -Force -Path $Root)
                        foreach ($d in @('core', 'gui', 'recursos', 'instalador')) {
                            $t = Join-Path $Root $d
                            if (Test-Path $t) { Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction SilentlyContinue }
                        }
                        $items = @(Get-ChildItem -LiteralPath $Src -Force | Where-Object { @('.venv', 'datos', '__pycache__', '.git', 'NOVA AI Setup.exe') -notcontains $_.Name })
                        $n = 0
                        foreach ($it in $items) {
                            $sync.Detail = 'Copiando ' + $it.Name
                            Copy-Item -LiteralPath $it.FullName -Destination $Root -Recurse -Force -ErrorAction Stop
                            $n++; Set-Frac (0.1 + 0.6 * $n / [Math]::Max($items.Count, 1))
                        }
                        [void](New-Item -ItemType Directory -Force -Path (Join-Path $Root 'datos'))
                        Copy-Item -LiteralPath (Join-Path $Src 'datos\comandos.json') -Destination (Join-Path $Root 'datos\comandos.json') -Force -ErrorAction Stop
                        Get-ChildItem -LiteralPath $Root -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
                            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                        Write-Log "Programa copiado a $Root"
                    }
                    # Los ejecutables (con su icono) van a la raíz: «NOVA AI.exe» y «Desinstalar NOVA AI.exe»
                    foreach ($e in @(Get-ChildItem -LiteralPath (Join-Path $Root 'instalador\bin') -Filter '*.exe' -ErrorAction SilentlyContinue)) {
                        try { Copy-Item -LiteralPath $e.FullName -Destination $Root -Force -ErrorAction Stop; Write-Log "Ejecutable: $($e.Name)" }
                        catch { Write-Log "No se pudo copiar $($e.Name): $($_.Exception.Message)" }
                    }
                    Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
                        Where-Object { $_.FullName -notlike '*\.venv\*' } | Unblock-File -ErrorAction SilentlyContinue
                    Set-Frac 0.8
                    # 3) Traer tus datos de una versión anterior: la carpeta datos\ junto al instalador o la
                    #    de la instalación antigua (la encuentra por su acceso directo «NOVA» del escritorio).
                    $cands = @(Join-Path $Src 'datos')
                    try {
                        $wsh0 = New-Object -ComObject WScript.Shell
                        foreach ($l in @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'NOVA.lnk'),
                                         (Join-Path ([Environment]::GetFolderPath('Programs')) 'NOVA.lnk'))) {
                            if (Test-Path $l) { $wd = $wsh0.CreateShortcut($l).WorkingDirectory; if ($wd) { $cands += (Join-Path $wd 'datos') } }
                        }
                    } catch {}
                    $oldData = $cands | Where-Object { Test-Path (Join-Path $_ 'ajustes.json') } | Select-Object -First 1
                    if ($oldData -and -not (Test-Path (Join-Path $UserData 'ajustes.json'))) {
                        $sync.Detail = 'Importando tus ajustes, comandos y memoria de la versión anterior…'
                        Get-ChildItem -LiteralPath $oldData -Force | Where-Object { @('comandos.json', 'interfaz', 'instalacion.log', 'ui_puerto.txt') -notcontains $_.Name } |
                            ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $UserData -Recurse -Force -ErrorAction SilentlyContinue }
                        Write-Log "Datos anteriores importados de $oldData"
                    }
                    $sync.Detail = 'Archivos en su sitio'
                }
                'pydl' {
                    $sync.Creep = $false
                    $sync.Detail = 'Conectando con python.org…'
                    Get-File $opts.PythonUrl $opts.PythonSetup
                }
                'pyinst' {
                    $sync.Detail = 'Instalando Python 3.12 para tu usuario (sin administrador)…'
                    $code = Invoke-Proc $opts.PythonSetup '/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_doc=0 Include_launcher=1 InstallLauncherAllUsers=0 Shortcuts=0' $null
                    if ($code -ne 0 -and $code -ne 3010) { throw "El instalador de Python devolvió el código $code" }
                    if (-not (Test-Path $opts.OwnPython)) { throw 'Python no aparece tras la instalación' }
                    $py = $opts.OwnPython
                    try { Remove-Item $opts.PythonSetup -Force } catch {}
                }
                'venv' {
                    $ok = $false
                    if (Test-Path $venvPy) {
                        $c = Invoke-Proc $venvPy '-c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)"' $null
                        $ok = ($c -eq 0)
                        if (-not $ok) { Write-Log 'Entorno dañado o de un Python no compatible: se vuelve a crear'; Remove-Item (Join-Path $Root '.venv') -Recurse -Force }
                    }
                    if ($ok) {
                        $sync.Detail = 'Entorno existente reutilizado (modo reparación)'
                    } else {
                        $sync.Detail = 'Creando entorno aislado de Python…'
                        $c = Invoke-Proc $py ('-m venv "' + (Join-Path $Root '.venv') + '"') $null
                        if ($c -ne 0 -or -not (Test-Path $venvPy)) { throw "No se pudo crear el entorno (código $c)" }
                    }
                }
                'pip' {
                    $sync.Detail = 'Actualizando pip…'
                    $c = Invoke-Proc $venvPy '-m pip install --upgrade pip' $pipLine
                    if ($c -ne 0) { Write-Log 'No se pudo actualizar pip; se continúa con el actual' }
                    $null = Invoke-Proc $venvPy '-c "import pip; print(pip.__version__)"' { param($l) $pst.PipVer = $l.Trim() }
                    $ver = $pst.PipVer
                    try {
                        $parts = ($ver -split '\.')
                        $sync.RawProgress = ([int]$parts[0] -gt 24) -or ([int]$parts[0] -eq 24 -and [int]$parts[1] -ge 1)
                    } catch { $sync.RawProgress = $false }
                    Write-Log "pip $ver · progreso detallado: $($sync.RawProgress)"
                }
                'pkg' { Install-Pkgs $s.Pkgs $s.MB }
                'config' {
                    $f = Join-Path $UserData 'ajustes.json'
                    $cfg = $null
                    if (Test-Path $f) { try { $cfg = Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json } catch {} }
                    if ($null -eq $cfg) { $cfg = New-Object PSObject }
                    $model = if ($opts.Cuda) { 'large-v3-turbo' } else { 'small' }
                    $cfg | Add-Member -NotePropertyName 'stt_modelo_local' -NotePropertyValue $model -Force
                    $json = $cfg | ConvertTo-Json -Depth 10
                    [IO.File]::WriteAllText($f, $json, (New-Object Text.UTF8Encoding($false)))
                    $sync.Detail = "Whisper local: modelo '$model'"
                }
                'verify' {
                    $sync.Detail = 'Comprobando que todo arranca…'
                    $mods = 'openai edge_tts miniaudio sounddevice numpy PIL requests rapidfuzz ddgs pygame faster_whisper pyttsx3'
                    if ($opts.Piper) { $mods += ' piper' }
                    $pst.Fails.Clear()
                    $codeLine = "import importlib`nfor m in '$mods'.split():`n    try:`n        importlib.import_module(m); print('OK', m)`n    except Exception as e:`n        print('FALLO', m, type(e).__name__, str(e)[:120])"
                    $tmp = Join-Path $env:TEMP 'nova_verificar.py'
                    [IO.File]::WriteAllText($tmp, $codeLine, (New-Object Text.UTF8Encoding($false)))
                    $null = Invoke-Proc $venvPy ('"' + $tmp + '"') { param($l) if ($l -match '^FALLO (\S+)') { [void]$pst.Fails.Add($Matches[1]) } }
                    $essential = @('openai', 'edge_tts', 'miniaudio', 'sounddevice', 'numpy', 'PIL', 'requests', 'rapidfuzz')
                    $bad = @($pst.Fails | Where-Object { $essential -contains $_ })
                    if ($bad.Count -gt 0) { throw ('Módulos imprescindibles que no cargan: ' + ($bad -join ', ')) }
                    if ($pst.Fails.Count -gt 0) {
                        $sync.Warn += 'Módulos opcionales con problemas: ' + (@($pst.Fails) -join ', ') + ". Nova funcionará sin ellos.`n"
                    }
                    # Precompilar: luego Nova arranca sin permisos de administrador y no puede escribir aquí.
                    $sync.Detail = 'Optimizando el arranque…'
                    $null = Invoke-Proc $venvPy ('-m compileall -q "' + (Join-Path $Root 'core') + '" "' + (Join-Path $Root 'gui') + '" "' + (Join-Path $Root 'nova.py') + '"') $null
                }
                'register' {
                    $sync.Detail = 'Registrando NOVA AI en Windows…'
                    $info = [ordered]@{ version = $opts.Version; fecha = (Get-Date -Format 'yyyy-MM-dd HH:mm'); carpeta = $Root; datos = $UserData
                                        normas_version = $opts.TermsVersion; normas_aceptadas = $opts.TermsAccepted }
                    [IO.File]::WriteAllText((Join-Path $Root 'instalado.json'), ($info | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
                    $exe = Join-Path $Root 'NOVA AI.exe'
                    $unExe = Join-Path $Root 'Desinstalar NOVA AI.exe'
                    $ico = (Join-Path $Root 'recursos\nova.ico') + ',0'
                    $wsh = New-Object -ComObject WScript.Shell
                    # Lanzador dentro de la carpeta (sirve para abrir Nova sin permisos de administrador)
                    $lnk = $wsh.CreateShortcut((Join-Path $Root 'NOVA AI.lnk'))
                    if (Test-Path $exe) { $lnk.TargetPath = $exe; $lnk.Arguments = ''; $ico = $exe + ',0' }
                    else { $lnk.TargetPath = Join-Path $Root '.venv\Scripts\pythonw.exe'; $lnk.Arguments = '"' + (Join-Path $Root 'nova.py') + '"' }
                    $lnk.WorkingDirectory = $Root; $lnk.IconLocation = $ico
                    $lnk.Description = 'NOVA AI · Asistente de vuelo para Star Citizen'; $lnk.Save()
                    # Desinstalador en «Aplicaciones instaladas» (Configuración de Windows y Panel de control)
                    $un = Join-Path $Root 'instalador\desinstalar.ps1'
                    $key = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NOVA AI'
                    [void](New-Item -Path $key -Force)
                    $size = 0
                    try { $size = [int]((Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1KB) } catch {}
                    $vals = @{
                        DisplayName = 'NOVA AI · Asistente de vuelo para Star Citizen'; DisplayVersion = $opts.Version
                        Publisher = 'Aaron B. Roldan (0zzyt0)'; DisplayIcon = $ico.Replace(',0', ''); InstallLocation = $Root
                        InstallDate = (Get-Date -Format 'yyyyMMdd')
                        UninstallString = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "' + $un + '"'
                        QuietUninstallString = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $un + '" -Silencioso'
                    }
                    if (Test-Path $unExe) {
                        $vals.UninstallString = '"' + $unExe + '"'
                        $vals.QuietUninstallString = '"' + $unExe + '" /S'
                    }
                    foreach ($k in $vals.Keys) { Set-ItemProperty -Path $key -Name $k -Value $vals[$k] }
                    Set-ItemProperty -Path $key -Name 'NoModify' -Value 1 -Type DWord
                    Set-ItemProperty -Path $key -Name 'NoRepair' -Value 1 -Type DWord
                    Set-ItemProperty -Path $key -Name 'EstimatedSize' -Value $size -Type DWord
                    Write-Log "Registrado el desinstalador ($key)"
                    $sync.Detail = 'Desinstalador registrado'
                }
                'shortcut' {
                    $wsh = New-Object -ComObject WScript.Shell
                    $pyw = Join-Path $Root '.venv\Scripts\pythonw.exe'
                    $exe = Join-Path $Root 'NOVA AI.exe'
                    $unExe = Join-Path $Root 'Desinstalar NOVA AI.exe'
                    $ico = (Join-Path $Root 'recursos\nova.ico') + ',0'
                    $unIco = (Join-Path $Root 'recursos\nova_desinstalar.ico') + ',0'
                    $desk = [Environment]::GetFolderPath('Desktop')
                    $menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'NOVA AI'
                    [void](New-Item -ItemType Directory -Force -Path $menu)
                    foreach ($old in @((Join-Path $desk 'NOVA.lnk'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'NOVA.lnk'))) {
                        if (Test-Path $old) { Remove-Item $old -Force -ErrorAction SilentlyContinue }  # de la versión anterior
                    }
                    foreach ($path in @((Join-Path $desk 'NOVA AI.lnk'), (Join-Path $menu 'NOVA AI.lnk'))) {
                        $lnk = $wsh.CreateShortcut($path)
                        if (Test-Path $exe) {
                            $lnk.TargetPath = $exe; $lnk.Arguments = ''; $lnk.IconLocation = $exe + ',0'
                        } else {
                            $lnk.TargetPath = $pyw; $lnk.Arguments = '"' + (Join-Path $Root 'nova.py') + '"'; $lnk.IconLocation = $ico
                        }
                        $lnk.WorkingDirectory = $Root
                        $lnk.Description = 'NOVA AI · Asistente de vuelo para Star Citizen'
                        $lnk.Save()
                    }
                    $lnk = $wsh.CreateShortcut((Join-Path $menu 'Desinstalar NOVA AI.lnk'))
                    if (Test-Path $unExe) {
                        $lnk.TargetPath = $unExe; $lnk.Arguments = ''; $lnk.IconLocation = $unExe + ',0'
                    } else {
                        $lnk.TargetPath = 'powershell.exe'
                        $lnk.Arguments = '-NoProfile -ExecutionPolicy Bypass -STA -File "' + (Join-Path $Root 'instalador\desinstalar.ps1') + '"'
                        $lnk.IconLocation = $unIco
                    }
                    $lnk.WorkingDirectory = $Root
                    $lnk.Description = 'Desinstalar NOVA AI'
                    $lnk.Save()
                    $sync.Detail = 'Escritorio y menú Inicio'
                }
            }
            $sync.StepFrac = 1.0
            $sync.States[$i] = 'done'
        } catch {
            $msg = $_.Exception.Message
            Write-Log "ERROR: $msg"
            if ($sync.Cancel) { return }
            if ($s.Optional) {
                $sync.States[$i] = 'warn'
                $sync.Warn += "$($s.Name): no se pudo completar (es opcional).`n"
            } else {
                $sync.States[$i] = 'error'
                $sync.Error = "$($s.Name): $msg"
                $sync.Failed = $true
                return
            }
        }
    }
    Write-Log '===== Instalación completada ====='
    $sync.Done = $true
}

# =================================================================  PLAN
function New-Plan {
    $d = $sync.Diag
    $p = New-Object System.Collections.ArrayList
    function Add-Step($id, $name, $secs, $mb = 0, $pkgs = $null, $optional = $false) {
        [void]$p.Add(@{ Id = $id; Name = $name; Secs = [double]$secs; MB = [double]$mb; Pkgs = $pkgs; Optional = $optional })
    }
    Add-Step 'prep' 'Copia a Archivos de programa' 6
    if (-not $d.PyExe) {
        Add-Step 'pydl' 'Descarga de Python 3.12' 8 25
        Add-Step 'pyinst' 'Instalación de Python 3.12' 55
    }
    Add-Step 'venv' 'Entorno aislado de Python' 12
    Add-Step 'pip' 'Actualización de pip' 10 2
    Add-Step 'pkg' 'Núcleo e inteligencia artificial' 25 35 @('openai>=1.40', 'requests>=2.31', 'numpy>=1.26', 'rapidfuzz>=3.0')
    Add-Step 'pkg' 'Audio y voces' 12 7 @('sounddevice>=0.4.6', 'miniaudio>=1.59', 'edge-tts>=7.0')
    Add-Step 'pkg' 'Voz de Windows (respaldo)' 4 1 @('pyttsx3>=2.90') $true
    Add-Step 'pkg' 'Interfaz y overlay' 8 10 @('pillow>=10.0')
    Add-Step 'pkg' 'Soporte de joystick y HOTAS' 12 12 @('pygame>=2.5') $true
    Add-Step 'pkg' 'Búsqueda en internet' 14 15 @('ddgs>=9.0') $true
    Add-Step 'pkg' 'Reconocimiento de voz local (Whisper)' 55 110 @('faster-whisper>=1.1') $true
    if ($ui.ChkPiper.IsChecked) { Add-Step 'pkg' 'Voz sin internet (Piper)' 20 25 @('piper-tts') $true }
    if ($ui.ChkCuda.IsChecked) { Add-Step 'pkg' 'Aceleración NVIDIA CUDA' 260 1100 @('nvidia-cublas-cu12', 'nvidia-cudnn-cu12==9.*') $true }
    Add-Step 'config' 'Configuración inicial' 1
    Add-Step 'verify' 'Verificación de sistemas' 12
    Add-Step 'register' 'Registro en Windows y desinstalador' 3
    if ($ui.ChkShortcut.IsChecked) { Add-Step 'shortcut' 'Accesos directos' 2 0 $null $true }
    return , $p
}

function Update-Estimate {
    if (-not $sync.DiagDone) { return }
    $plan = New-Plan
    $mb = 0.0; $secs = 0.0
    foreach ($s in $plan) { $mb += $s.MB; $secs += $s.Secs }
    $ui.EstimateText.Text = 'Descarga estimada ≈ {0:N0} MB  ·  Tiempo estimado ≈ {1} (según tu conexión)' -f $mb, (Format-Duration $secs)
}

# ===========================================================  INTERFAZ: PASOS
$script:rows = @()
function Build-Steps($plan) {
    $ui.StepsList.Children.Clear()
    $script:rows = @()
    foreach ($s in $plan) {
        $g = New-Object Windows.Controls.Grid
        $g.Margin = '0,1,0,1'
        foreach ($w in @(28, 0, 120)) {
            $cd = New-Object Windows.Controls.ColumnDefinition
            if ($w -eq 0) { $cd.Width = New-Object Windows.GridLength(1, 'Star') } else { $cd.Width = New-Object Windows.GridLength($w) }
            $g.ColumnDefinitions.Add($cd)
        }
        $icon = New-Object Windows.Controls.TextBlock
        $icon.Text = '◇'; $icon.FontSize = 13
        $name = New-Object Windows.Controls.TextBlock
        $name.Text = $s.Name; $name.FontSize = 13
        $state = New-Object Windows.Controls.TextBlock
        $state.FontFamily = 'Consolas'; $state.FontSize = 12; $state.HorizontalAlignment = 'Right'
        [Windows.Controls.Grid]::SetColumn($name, 1)
        [Windows.Controls.Grid]::SetColumn($state, 2)
        [void]$g.Children.Add($icon); [void]$g.Children.Add($name); [void]$g.Children.Add($state)
        [void]$ui.StepsList.Children.Add($g)
        $script:rows += , @{ Icon = $icon; Name = $name; State = $state; Last = '' }
        Set-Color $icon '#3F6A82'; Set-Color $name '#5F8AA2'; Set-Color $state '#3F6A82'
    }
}

function Update-Steps {
    $states = $sync.States
    for ($i = 0; $i -lt $script:rows.Count; $i++) {
        $r = $script:rows[$i]
        $st = $states[$i]
        if ($st -eq 'active') {
            $pctStep = [Math]::Floor(100 * $script:curStepFrac)
            $r.State.Text = 'EN CURSO {0,3}%' -f [int]$pctStep
        }
        if ($r.Last -eq $st) { continue }
        $r.Last = $st
        switch ($st) {
            'active' { $r.Icon.Text = '◆'; Set-Color $r.Icon '#8FE4FF'; Set-Color $r.Name '#FFFFFF'; Set-Color $r.State '#8FE4FF'
                       $r.Icon.Effect = $window.Resources['GlowSoft'] }
            'done'   { $r.Icon.Text = '✓'; Set-Color $r.Icon '#3FD8A8'; Set-Color $r.Name '#9FC8DA'; Set-Color $r.State '#3FD8A8'
                       $r.State.Text = 'OK'; $r.Icon.Effect = $null }
            'warn'   { $r.Icon.Text = '⚠'; Set-Color $r.Icon '#E8C15A'; Set-Color $r.Name '#E8D9A8'; Set-Color $r.State '#E8C15A'
                       $r.State.Text = 'OMITIDO'; $r.Icon.Effect = $null }
            'error'  { $r.Icon.Text = '✕'; Set-Color $r.Icon '#FF6B7A'; Set-Color $r.Name '#FFC7CD'; Set-Color $r.State '#FF6B7A'
                       $r.State.Text = 'FALLO'; $r.Icon.Effect = $null }
            default  { $r.Icon.Text = '◇'; Set-Color $r.Icon '#3F6A82'; Set-Color $r.Name '#5F8AA2'; $r.State.Text = '' }
        }
    }
}

# ==========================================================  INTERFAZ: BUCLE
$script:phase = 'diag'      # diag -> options -> install -> done | error
$script:plan = $null
$script:totalSecs = 1.0
$script:startTime = [DateTime]::Now
$script:shownP = 0.0
$script:eta = -1.0
$script:curStepFrac = 0.0
$script:subtitleFull = 'PROTOCOLO DE INSTALACIÓN  //  ASISTENTE DE VUELO PARA STAR CITIZEN'
$script:typed = 0
$script:spoke = $false

function Get-Progress {
    if ($sync.Done) { return 1.0 }
    $idx = [int]$sync.StepIndex
    if ($idx -lt 0) { return 0.0 }
    $done = 0.0
    for ($i = 0; $i -lt [Math]::Min($idx, $script:plan.Count); $i++) { $done += $script:plan[$i].Secs }
    $f = [double]$sync.StepFrac
    if ($idx -lt $script:plan.Count) {
        if ($sync.Creep -and $f -lt 1.0) {
            $t = ([DateTime]::Now - $sync.StepStart).TotalSeconds
            $exp = [Math]::Max(1.0, $script:plan[$idx].Secs)
            $creep = 0.95 * (1 - [Math]::Exp(-1.5 * $t / $exp))
            $f = [Math]::Max($f, $creep)
        }
        $script:curStepFrac = $f
        $done += $script:plan[$idx].Secs * $f
    }
    return [Math]::Min(1.0, $done / $script:totalSecs)
}

function Show-Panel([string]$name) {
    foreach ($n in 'PanelTerms', 'PanelOptions', 'PanelSteps', 'PanelDone', 'PanelError') {
        $ui[$n].Visibility = if ($n -eq $name) { 'Visible' } else { 'Collapsed' }
    }
}

function Set-Diag($el, [bool]$ok, [string]$text, [bool]$warn = $false) {
    if ($ok) { $el.Text = '✓  ' + $text; Set-Color $el '#9FE8D0' }
    elseif ($warn) { $el.Text = '⚠  ' + $text; Set-Color $el '#E8C15A' }
    else { $el.Text = '✕  ' + $text; Set-Color $el '#FF8B96' }
}

function On-Tick {
    # Reloj "del 'verso" (el calendario de Star Citizen va 930 años por delante)
    $now = Get-Date
    $ui.Clock.Text = 'UEE · STANTON · {0}-{1:MM-dd HH:mm:ss}' -f ($now.Year + 930), $now

    if ($script:typed -lt $script:subtitleFull.Length) {
        $script:typed = [Math]::Min($script:subtitleFull.Length, $script:typed + 2)
        $ui.Subtitle.Text = $script:subtitleFull.Substring(0, $script:typed) + $(if ($script:typed -lt $script:subtitleFull.Length) { '▌' } else { '' })
    }

    # Registro técnico
    $line = $null
    $added = $false
    while ($sync.Log.TryDequeue([ref]$line)) { $ui.LogBox.AppendText($line + "`r`n"); $added = $true }
    if ($added) {
        if ($ui.LogBox.Text.Length -gt 80000) { $ui.LogBox.Text = $ui.LogBox.Text.Substring($ui.LogBox.Text.Length - 50000) }
        $ui.LogBox.ScrollToEnd()
    }

    switch ($script:phase) {
        'diag' {
            $ui.EtaSmall.Text = 'ESCANEANDO…'
            $p = (([DateTime]::Now - $script:startTime).TotalSeconds % 2.0) / 2.0
            Set-Arc $p
            if ($sync.DiagDone) {
                $d = $sync.Diag
                if ($d.PyExe) { Set-Diag $ui.DiagPython $true ("Python {0} detectado" -f $d.PyVer) }
                elseif ($d.OtherVer) { Set-Diag $ui.DiagPython $false ("Python {0} es demasiado nuevo para las librerías · se instalará Python 3.12 aparte, sin tocar el tuyo (≈ 25 MB)" -f $d.OtherVer) $true }
                else { Set-Diag $ui.DiagPython $false 'Python no encontrado · se instalará automáticamente (≈ 25 MB)' $true }
                if ($d.Nvidia) {
                    Set-Diag $ui.DiagGpu $true ($d.Gpu + ' · aceleración disponible')
                    $ui.ChkCuda.IsChecked = $true
                } else {
                    $g = if ($d.Gpu) { $d.Gpu } else { 'desconocida' }
                    Set-Diag $ui.DiagGpu $false ("$g · sin CUDA: el reconocimiento usará Groq o la CPU") $true
                    $ui.ChkCuda.IsChecked = $false; $ui.ChkCuda.IsEnabled = $false
                    $ui.ChkCudaSub.Text = 'Requiere una tarjeta NVIDIA'
                }
                if ($d.FreeGB -lt 0) { Set-Diag $ui.DiagDisk $false 'Espacio libre desconocido' $true }
                elseif ($d.FreeGB -lt 3) { Set-Diag $ui.DiagDisk $false ('Solo {0:N1} GB libres · se recomiendan 3 GB (5 GB con CUDA)' -f $d.FreeGB) $true }
                else { Set-Diag $ui.DiagDisk $true ('{0:N1} GB libres' -f $d.FreeGB) }
                if ($d.Net) { Set-Diag $ui.DiagNet $true 'Conexión con los repositorios establecida' }
                else { Set-Diag $ui.DiagNet $false 'Sin conexión con pypi.org · revisa internet o el firewall' }
                if ($d.Repair) { $ui.Subtitle.Text = 'INSTALACIÓN PREVIA DETECTADA  //  MODO REPARACIÓN Y ACTUALIZACIÓN'; $script:typed = 999 }
                if ($Actualizar) { $ui.Subtitle.Text = 'ACTUALIZANDO NOVA AI A LA VERSIÓN ' + $AppVersion; $script:typed = 999 }
                $ui.BtnStart.IsEnabled = $true
                Update-Estimate
                Set-Arc 0.001
                $ui.EtaSmall.Text = 'EN ESPERA'
                $script:phase = 'options'
                # Actualización desde NOVA: empieza sola en cuanto las normas están aceptadas
                if ($Actualizar -and $script:termsAccepted) { Start-Install }
            }
        }
        'install' {
            $p = Get-Progress
            $script:shownP += ($p - $script:shownP) * 0.25
            if ($script:shownP -gt $p) { $script:shownP = $p }
            $sp = $script:shownP
            Set-Arc $sp
            $pct = [int][Math]::Floor($sp * 100)
            $ui.Pct.Text = "$pct"
            $ui.PctFooter.Text = "$pct %"
            $w = $ui.BarTrack.ActualWidth * $sp
            if ($w -ge 0) { $ui.BarFill.Width = $w }

            $elapsed = ([DateTime]::Now - $script:startTime).TotalSeconds
            $ui.Elapsed.Text = Format-Clock $elapsed
            if ($elapsed -gt 4 -and $p -gt 0.02) {
                $factor = $elapsed / [Math]::Max($p * $script:totalSecs, 1.0)
                $factor = [Math]::Max(0.3, [Math]::Min($factor, 6.0))
                $raw = (1 - $p) * $script:totalSecs * $factor
                if ($script:eta -lt 0) { $script:eta = $raw } else { $script:eta = 0.92 * ($script:eta - 0.1) + 0.08 * $raw }
                $ui.Remaining.Text = '≈ ' + (Format-Duration $script:eta)
                $ui.EtaSmall.Text = 'T-  ' + (Format-Clock $script:eta)
            } else {
                $ui.Remaining.Text = 'calculando…'
                $ui.EtaSmall.Text = 'CALCULANDO…'
            }
            $speed = [double]$sync.Speed
            $ui.Speed.Text = if ($speed -gt 0.05) { '{0:N1} MB/s' -f $speed } else { '—' }
            $ui.StatusText.Text = $sync.Status
            $ui.DetailText.Text = $sync.Detail
            Update-Steps

            if ($sync.Done) { Finish-Install }
            elseif ($sync.Failed) { Fail-Install }
        }
    }
}

function Start-Install {
    if (-not $sync.Diag.PyExe -and (Test-Path $OwnPython)) { $sync.Diag.PyExe = $OwnPython }
    $script:plan = New-Plan
    $script:totalSecs = 0.0
    foreach ($s in $script:plan) { $script:totalSecs += $s.Secs }
    $sync.States = New-Object string[] $script:plan.Count
    $sync.StepIndex = -1; $sync.StepFrac = 0.0; $sync.Done = $false; $sync.Failed = $false
    $sync.Error = ''; $sync.Warn = ''; $sync.Cancel = $false
    $script:startTime = [DateTime]::Now
    $script:shownP = 0.0
    $script:eta = -1.0
    Set-Arc 0.001
    Build-Steps $script:plan
    Show-Panel 'PanelSteps'
    $ui.Arc.Stroke = New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString('#6FD8FF'))
    $opts = @{
        PyExe = $sync.Diag.PyExe
        PythonUrl = $PythonUrl
        PythonSetup = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
        OwnPython = $OwnPython
        Cuda = [bool]$ui.ChkCuda.IsChecked
        Piper = [bool]$ui.ChkPiper.IsChecked
        Src = $Src
        UserData = $UserData
        Version = $AppVersion
        TermsVersion = $TermsVersion
        TermsAccepted = $script:termsAccepted
    }
    $script:phase = 'install'
    $ui.BtnPath.IsEnabled = $false
    Start-Background $worker @($sync, $script:plan, $script:Root, $opts)
}

function Finish-Install {
    $script:phase = 'done'
    Set-Arc 0.9999
    $ui.Pct.Text = '100'; $ui.PctFooter.Text = '100 %'
    $ui.BarFill.Width = $ui.BarTrack.ActualWidth
    $ui.EtaSmall.Text = 'SISTEMAS EN LÍNEA'
    $ui.Remaining.Text = 'completado'
    $ui.Speed.Text = '—'
    Update-Steps
    $ui.DoneText.Text = ('NOVA AI está lista para el despegue. Tiempo total: {0}.' -f (Format-Duration ([DateTime]::Now - $script:startTime).TotalSeconds)) +
        "`n`nInstalada en: $($script:Root)" +
        $(if ($ui.ChkShortcut.IsChecked) { "`nAcceso directo «NOVA AI» en el escritorio y en el menú Inicio." } else { '' }) +
        "`nPara desinstalarla: menú Inicio › NOVA AI › Desinstalar, o Configuración › Aplicaciones." +
        "`n`nAl abrirla por primera vez te guiará para ponerle nombre y entrenar su oído con tu voz."
    $ui.DoneWarn.Text = $sync.Warn.Trim()
    Show-Panel 'PanelDone'
    try { [Media.SystemSounds]::Asterisk.Play() } catch {}
    if (-not $script:spoke) {
        $script:spoke = $true
        try {
            Add-Type -AssemblyName System.Speech
            $script:synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $es = $script:synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1
            if ($es) {
                $script:synth.SelectVoice($es.VoiceInfo.Name)
                $script:synth.SpeakAsync('Instalación completada. Nova lista para el despegue, señor.') | Out-Null
            }
        } catch {}
    }
    if ($SinIniciar) {
        $script:autoCloseAt = [DateTime]::Now.AddSeconds(6)  # actualizada «al cerrar»: no se vuelve a abrir
    } elseif ($ui.ChkLaunch.IsChecked -or $Actualizar) {
        $script:autoLaunchAt = [DateTime]::Now.AddSeconds(4)
    }
}

function Fail-Install {
    $script:phase = 'error'
    Update-Steps
    $ui.Arc.Stroke = New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString('#FF6B7A'))
    $ui.EtaSmall.Text = 'FALLO'
    $ui.Remaining.Text = '—'
    $ui.ErrorText.Text = $sync.Error
    $tail = @($ui.LogBox.Text -split "`r`n" | Where-Object { $_ } | Select-Object -Last 5) -join "`n"
    $ui.ErrorTail.Text = $tail
    Show-Panel 'PanelError'
    try { [Media.SystemSounds]::Hand.Play() } catch {}
}

function Start-Nova {
    # El instalador corre como administrador; Nova debe abrirse como usuario normal.
    # Abrir el acceso directo con el Explorador la lanza con tus permisos de siempre.
    $lnk = Join-Path $script:Root 'NOVA AI.lnk'
    if (Test-Path $lnk) {
        Start-Process -FilePath "$env:WINDIR\explorer.exe" -ArgumentList ('"' + $lnk + '"')
    }
}

# ===========================================================  NORMAS
$TermsVersion = '1.2'
$script:termsAccepted = ''
function Add-TermsLine([string]$text, [string]$kind) {
    $tb = New-Object Windows.Controls.TextBlock
    $tb.TextWrapping = 'Wrap'
    $tb.Text = ($text -replace '\*\*', '' -replace '`', '')
    $brush = { param($hex) New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString($hex)) }
    switch ($kind) {
        'h1' { $tb.FontSize = 17; $tb.FontWeight = 'Bold'; $tb.Foreground = (& $brush '#DFF7FF'); $tb.Margin = '0,0,0,2' }
        'h2' { $tb.FontSize = 12; $tb.FontWeight = 'SemiBold'; $tb.Foreground = (& $brush '#20B8E8'); $tb.Margin = '0,12,0,4' }
        'li' { $tb.FontSize = 13; $tb.Foreground = (& $brush '#CFEFFF'); $tb.Margin = '10,2,0,2'; $tb.Text = '◆  ' + $tb.Text }
        'dim' { $tb.FontSize = 12; $tb.Foreground = (& $brush '#6F93A8'); $tb.Margin = '0,0,0,4' }
        default { $tb.FontSize = 13; $tb.Foreground = (& $brush '#CFEFFF'); $tb.Margin = '0,3,0,3' }
    }
    [void]$ui.TermsBody.Children.Add($tb)
}
try {
    $termsFile = Join-Path $Src 'NORMAS_Y_PRIVACIDAD.md'
    $lines = if (Test-Path $termsFile) { [IO.File]::ReadAllLines($termsFile, [Text.Encoding]::UTF8) } else { @() }
    if ($lines.Count -eq 0) {
        $lines = @('# NOVA AI · Normas de uso y Política de privacidad',
                   '- Tus datos se quedan en tu PC (%LOCALAPPDATA%\NOVA AI\datos). NOVA AI no tiene servidores ni telemetría y no comparte tus datos.',
                   '- No se hacen grabaciones: tu voz no se guarda en ningún archivo.',
                   '- Lo que le pides a Nova se envía como texto al servicio de IA que uses, como si lo escribieras tú en su web.',
                   '- Proyecto de fans sin afiliación con Cloud Imperium Games. Se ofrece gratis y tal cual, sin garantías.')
    }
    foreach ($l in $lines) {
        $t = $l.TrimEnd()
        if (-not $t) { continue }
        if ($t.StartsWith('## ')) { Add-TermsLine $t.Substring(3).ToUpper() 'h2' }
        elseif ($t.StartsWith('# ')) { Add-TermsLine $t.Substring(2) 'h1' }
        elseif ($t.StartsWith('- ')) { Add-TermsLine $t.Substring(2) 'li' }
        elseif ($t -match '^Versión') { Add-TermsLine $t 'dim' }
        else { Add-TermsLine $t 'p' }
    }
} catch {
    Add-TermsLine ('No se pudieron cargar las normas: ' + $_.Exception.Message) 'p'
}
$ui.ChkTerms.Add_Checked({ $ui.BtnAccept.IsEnabled = $true })
$ui.ChkTerms.Add_Unchecked({ $ui.BtnAccept.IsEnabled = $false })
$ui.BtnAccept.Add_Click({
    $script:termsAccepted = Get-Date -Format 'yyyy-MM-dd HH:mm'
    Show-Panel 'PanelOptions'
    if ($Actualizar -and $script:phase -eq 'options') { Start-Install }
})
# Al actualizar: si ya aceptaste estas mismas normas, no se vuelven a pedir
if ($Actualizar) {
    try {
        $prev = Get-Content -LiteralPath (Join-Path $Root 'instalado.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($prev.normas_version -eq $TermsVersion -and $prev.normas_aceptadas) {
            $script:termsAccepted = [string]$prev.normas_aceptadas
            Show-Panel 'PanelOptions'
        }
    } catch {}
}
$ui.BtnDecline.Add_Click({ $window.Close() })

# ===========================================================  EVENTOS
$ui.Header.Add_MouseLeftButtonDown({ try { $window.DragMove() } catch {} })
$ui.BtnMin.Add_Click({ $window.WindowState = 'Minimized' })
$ui.BtnClose.Add_Click({ $window.Close() })
$ui.BtnFinish.Add_Click({ $window.Close() })
$ui.BtnStart.Add_Click({ Start-Install })
$ui.BtnRetry.Add_Click({ Start-Install })
$ui.BtnLaunch.Add_Click({ $script:autoLaunchAt = $null; Start-Nova; $window.Close() })
$ui.BtnOpenLog.Add_Click({
    $f = Join-Path $UserData 'instalacion.log'
    if (Test-Path $f) { Start-Process notepad.exe -ArgumentList ('"' + $f + '"') }
})
$ui.BtnPath.Add_Click({
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = 'Elige dónde instalar NOVA AI (se creará la carpeta «NOVA AI» dentro)'
        $dlg.SelectedPath = Split-Path -Parent $script:Root
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $p = $dlg.SelectedPath
            if ((Split-Path -Leaf $p) -ne $AppName) { $p = Join-Path $p $AppName }
            $script:Root = $p
            Show-Destination
        }
    } catch {}
})
$ui.BtnLogToggle.Add_Click({
    if ($ui.LogBorder.Visibility -eq 'Visible') {
        $ui.LogBorder.Visibility = 'Collapsed'; $ui.BtnLogToggle.Content = '▸ REGISTRO TÉCNICO'
    } else {
        $ui.LogBorder.Visibility = 'Visible'; $ui.BtnLogToggle.Content = '▾ REGISTRO TÉCNICO'
    }
})
foreach ($chk in @($ui.ChkCuda, $ui.ChkPiper, $ui.ChkShortcut)) {
    $chk.Add_Checked({ Update-Estimate })
    $chk.Add_Unchecked({ Update-Estimate })
}

$window.Add_Closing({
    param($sender, $e)
    if ($script:phase -eq 'install') {
        $answer = [Windows.MessageBox]::Show('La instalación está en curso. ¿Seguro que quieres cancelarla?',
            'NOVA', 'YesNo', 'Warning')
        if ($answer -ne 'Yes') { $e.Cancel = $true; return }
        $sync.Cancel = $true
        if ($sync.ChildPid) { try { Stop-Process -Id $sync.ChildPid -Force } catch {} }
    }
})

$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(100)
$script:autoLaunchAt = $null
$script:autoCloseAt = $null
$script:lastUiError = ''
$timer.Add_Tick({
    try {
        On-Tick
        if ($script:autoLaunchAt -and [DateTime]::Now -ge $script:autoLaunchAt) {
            $script:autoLaunchAt = $null
            Start-Nova
            $window.Close()
        }
        if ($script:autoCloseAt -and [DateTime]::Now -ge $script:autoCloseAt) {
            $script:autoCloseAt = $null
            $window.Close()
        }
    } catch {
        $m = $_.Exception.Message
        if ($m -ne $script:lastUiError) { $script:lastUiError = $m; $sync.Log.Enqueue('[interfaz] ' + $m) }
    }
})

$window.Add_Loaded({
    # Aviso para «NOVA AI Setup.exe»: la ventana se ha abierto bien.
    if ($env:NOVA_SETUP_READY) { try { [IO.File]::WriteAllText($env:NOVA_SETUP_READY, 'ok') } catch {} }
    $timer.Start()
    Show-Destination
    Start-Background $detect @($sync, $script:Root, $OwnPython)
})

[void]$window.ShowDialog()
$timer.Stop()
foreach ($r in $script:runspaces) { try { $r[0].Stop(); $r[0].Dispose() } catch {} }
exit 0
