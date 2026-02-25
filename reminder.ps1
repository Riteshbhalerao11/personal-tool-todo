# reminder.ps1 - Login popup with streak, greeting, and motivational quote/roast

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

# --- Load libraries ---
$libDir = Join-Path $PSScriptRoot "lib"
. "$libDir\quotes.ps1"
. "$libDir\markdown.ps1"
. "$libDir\streak.ps1"

# Ensure data folder exists
Initialize-TodoFolder

# --- Check if already shown today ---
if (Test-ReminderShownToday) {
    exit
}

# Mark as shown
Set-ReminderShown

# --- Gather content ---
$streakInfo = Update-StreakFromTodos
$streakDisplay = Get-StreakDisplay
$greeting = Get-TimeGreeting

if ($streakInfo.IsBroken) {
    $quoteText = Get-GentleRoast
    $quoteAuthor = ""
} else {
    $q = Get-MotivationalQuote
    $quoteText = $q.Text
    $quoteAuthor = $q.Author
}

# --- Catppuccin Mocha palette ---
$theme = @{
    Base     = "#1e1e2e"
    Mantle   = "#181825"
    Surface0 = "#313244"
    Surface1 = "#45475a"
    Text     = "#cdd6f4"
    Subtext0 = "#a6adc8"
    Subtext1 = "#bac2de"
    Green    = "#a6e3a1"
    Red      = "#f38ba8"
    Peach    = "#fab387"
    Mauve    = "#cba6f7"
    Overlay0 = "#6c7086"
    Crust    = "#11111b"
}

# --- XAML ---
$xaml = @"
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Daily Todo Reminder"
    Width="400" Height="280"
    WindowStyle="None"
    AllowsTransparency="True"
    Background="Transparent"
    Topmost="True"
    ShowInTaskbar="True"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize">
    <Border CornerRadius="16" Background="$($theme.Base)" BorderBrush="$($theme.Surface1)" BorderThickness="1">
        <Border.Effect>
            <DropShadowEffect BlurRadius="24" ShadowDepth="3" Opacity="0.6" Color="#000000"/>
        </Border.Effect>
        <Grid Margin="24">
            <Grid.RowDefinitions>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="*"/>
                <RowDefinition Height="Auto"/>
            </Grid.RowDefinitions>

            <!-- Greeting -->
            <TextBlock Grid.Row="0" Name="TxtGreeting" FontSize="18" FontWeight="Bold" Foreground="$($theme.Mauve)"
                HorizontalAlignment="Center" Margin="0,0,0,8" TextWrapping="Wrap"/>

            <!-- Streak -->
            <TextBlock Grid.Row="1" Name="TxtStreak" FontSize="14" FontWeight="SemiBold" Foreground="$($theme.Peach)"
                HorizontalAlignment="Center" Margin="0,0,0,12" TextWrapping="Wrap"/>

            <!-- Quote -->
            <Border Grid.Row="2" Background="$($theme.Mantle)" CornerRadius="8" Padding="14,10" Margin="0,0,0,16">
                <TextBlock Name="TxtQuote" FontSize="12" Foreground="$($theme.Subtext1)" FontStyle="Italic"
                    TextWrapping="Wrap" HorizontalAlignment="Center" TextAlignment="Center"/>
            </Border>

            <!-- Spacer -->
            <Grid Grid.Row="3"/>

            <!-- Buttons -->
            <StackPanel Grid.Row="4" Orientation="Horizontal" HorizontalAlignment="Center">
                <Button Name="BtnOpen" Content="Open Todo Widget" Padding="16,8" FontSize="13" FontWeight="SemiBold"
                    Foreground="$($theme.Crust)" Background="$($theme.Green)" BorderThickness="0" Cursor="Hand" Margin="0,0,12,0">
                    <Button.Resources>
                        <Style TargetType="Border">
                            <Setter Property="CornerRadius" Value="8"/>
                        </Style>
                    </Button.Resources>
                </Button>
                <Button Name="BtnDismiss" Content="Not now" Padding="16,8" FontSize="13"
                    Foreground="$($theme.Subtext0)" Background="$($theme.Surface0)" BorderThickness="0" Cursor="Hand">
                    <Button.Resources>
                        <Style TargetType="Border">
                            <Setter Property="CornerRadius" Value="8"/>
                        </Style>
                    </Button.Resources>
                </Button>
            </StackPanel>
        </Grid>
    </Border>
</Window>
"@

# --- Build window ---
$reader = [System.Xml.XmlReader]::Create([System.IO.StringReader]::new($xaml))
$window = [System.Windows.Markup.XamlReader]::Load($reader)

$txtGreetingCtrl = $window.FindName("TxtGreeting")
$txtStreakCtrl   = $window.FindName("TxtStreak")
$txtQuoteCtrl   = $window.FindName("TxtQuote")
$btnOpen         = $window.FindName("BtnOpen")
$btnDismiss      = $window.FindName("BtnDismiss")

# --- Set content ---
$txtGreetingCtrl.Text = $greeting
$txtStreakCtrl.Text = $streakDisplay
if ($quoteAuthor) {
    $txtQuoteCtrl.Text = "`"$quoteText`"`n- $quoteAuthor"
} else {
    $txtQuoteCtrl.Text = $quoteText
}

# --- Auto-dismiss timer (30 seconds) ---
$autoCloseTimer = [System.Windows.Threading.DispatcherTimer]::new()
$autoCloseTimer.Interval = [TimeSpan]::FromSeconds(30)
$autoCloseTimer.Add_Tick({
    $autoCloseTimer.Stop()
    $window.Close()
})
$autoCloseTimer.Start()

# --- Button actions ---
$btnOpen.Add_Click({
    $autoCloseTimer.Stop()
    $window.Close()
    # Launch widget
    $widgetPath = Join-Path $PSScriptRoot "widget.ps1"
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$widgetPath`""
})

$btnDismiss.Add_Click({
    $autoCloseTimer.Stop()
    $window.Close()
})

# Draggable
$window.Add_MouseLeftButtonDown({
    $window.DragMove()
})

# --- Show ---
$window.ShowDialog() | Out-Null
