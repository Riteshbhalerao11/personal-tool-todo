# widget.ps1 - Main floating WPF Todo Widget (Catppuccin Mocha dark theme)

param([switch]$NoMutex)

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

# --- Single instance check via named mutex ---
$mutexName = "Global\TodoWidgetMutex_RB"
$script:mutex = $null
if (-not $NoMutex) {
    $createdNew = $false
    $script:mutex = [System.Threading.Mutex]::new($true, $mutexName, [ref]$createdNew)
    if (-not $createdNew) {
        Write-Host "Widget is already running."
        exit
    }
}

# --- Write PID file so todo-down can find us ---
$pidFile = Join-Path $PSScriptRoot "widget.pid"
[System.IO.File]::WriteAllText($pidFile, "$PID")

# --- Load libraries ---
$libDir = Join-Path $PSScriptRoot "lib"
. "$libDir\quotes.ps1"
. "$libDir\markdown.ps1"
. "$libDir\streak.ps1"

# Ensure data folder/files exist
Initialize-TodoFolder

# --- Catppuccin Mocha palette ---
$theme = @{
    Base     = "#1e1e2e"
    Mantle   = "#181825"
    Crust    = "#11111b"
    Surface0 = "#313244"
    Surface1 = "#45475a"
    Surface2 = "#585b70"
    Text     = "#cdd6f4"
    Subtext0 = "#a6adc8"
    Subtext1 = "#bac2de"
    Green    = "#a6e3a1"
    Red      = "#f38ba8"
    Peach    = "#fab387"
    Yellow   = "#f9e2af"
    Mauve    = "#cba6f7"
    Blue     = "#89b4fa"
    Overlay0 = "#6c7086"
}

# --- XAML UI ---
$xaml = @"
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Todo Widget"
    Width="380" Height="520"
    MinWidth="300" MinHeight="350"
    WindowStyle="None"
    AllowsTransparency="True"
    Background="Transparent"
    Topmost="False"
    ShowInTaskbar="False"
    ResizeMode="CanResizeWithGrip">
    <Border CornerRadius="16" Background="$($theme.Base)" BorderBrush="$($theme.Surface1)" BorderThickness="1">
        <Border.Effect>
            <DropShadowEffect BlurRadius="20" ShadowDepth="2" Opacity="0.5" Color="#000000"/>
        </Border.Effect>
        <Grid Margin="16,16,16,4">
            <Grid.RowDefinitions>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="*"/>
                <RowDefinition Height="Auto"/>
            </Grid.RowDefinitions>

            <!-- Row 0: Title Bar (drag handle only) -->
            <Grid Grid.Row="0" Name="TitleBar" Background="Transparent" Margin="0,0,0,8">
                <TextBlock Text="Todo Widget" FontSize="18" FontWeight="Bold" Foreground="$($theme.Mauve)" VerticalAlignment="Center" FontFamily="Segoe UI"/>
            </Grid>

            <!-- Row 1: Streak + Greeting -->
            <StackPanel Grid.Row="1" Margin="0,0,0,6">
                <TextBlock Name="TxtStreak" FontSize="15" FontWeight="Bold" Foreground="$($theme.Peach)" TextWrapping="Wrap" FontFamily="Segoe UI"/>
                <TextBlock Name="TxtGreeting" FontSize="12" Foreground="$($theme.Subtext0)" Margin="0,3,0,0" TextWrapping="Wrap" FontFamily="Segoe UI"/>
            </StackPanel>

            <!-- Row 2: Quote of the Day -->
            <Border Grid.Row="2" Background="$($theme.Mantle)" CornerRadius="10" Padding="12,10" Margin="0,4,0,10">
                <StackPanel>
                    <TextBlock Name="TxtQuote" FontSize="12" Foreground="$($theme.Subtext1)" FontStyle="Italic" TextWrapping="Wrap" FontFamily="Segoe UI" LineHeight="18"/>
                    <TextBlock Name="TxtQuoteAuthor" FontSize="10" Foreground="$($theme.Overlay0)" Margin="0,4,0,0" HorizontalAlignment="Right" FontFamily="Segoe UI"/>
                </StackPanel>
            </Border>

            <!-- Row 3: Scrollable Todo List -->
            <Border Grid.Row="3" Background="$($theme.Mantle)" CornerRadius="10" Padding="6" Margin="0,0,0,10">
                <ScrollViewer VerticalScrollBarVisibility="Auto">
                    <StackPanel Name="TodoList"/>
                </ScrollViewer>
            </Border>

            <!-- Row 4: Add Todo Input -->
            <Grid Grid.Row="4" Margin="0,0,0,10">
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>
                <TextBox Grid.Column="0" Name="TxtNewTodo" FontSize="13" Padding="10,8" FontFamily="Segoe UI"
                    Background="$($theme.Surface0)" Foreground="$($theme.Text)" BorderBrush="$($theme.Surface1)"
                    BorderThickness="1" VerticalContentAlignment="Center">
                    <TextBox.Resources>
                        <Style TargetType="Border">
                            <Setter Property="CornerRadius" Value="10"/>
                        </Style>
                    </TextBox.Resources>
                </TextBox>
                <Button Grid.Column="1" Name="BtnAdd" Content="+" Width="38" Height="38" Margin="8,0,0,0"
                    FontSize="22" FontWeight="Bold" Foreground="$($theme.Crust)" Background="$($theme.Green)"
                    BorderThickness="0" Cursor="Hand" ToolTip="Add todo" FontFamily="Segoe UI">
                    <Button.Resources>
                        <Style TargetType="Border">
                            <Setter Property="CornerRadius" Value="10"/>
                        </Style>
                    </Button.Resources>
                </Button>
            </Grid>
        </Grid>
    </Border>
</Window>
"@

# --- Parse XAML ---
$reader = [System.Xml.XmlReader]::Create([System.IO.StringReader]::new($xaml))
$window = [System.Windows.Markup.XamlReader]::Load($reader)

# --- Find controls ---
$titleBar       = $window.FindName("TitleBar")
$txtStreak      = $window.FindName("TxtStreak")
$txtGreeting    = $window.FindName("TxtGreeting")
$txtQuote       = $window.FindName("TxtQuote")
$txtQuoteAuthor = $window.FindName("TxtQuoteAuthor")
$todoList       = $window.FindName("TodoList")
$txtNewTodo  = $window.FindName("TxtNewTodo")
$btnAdd      = $window.FindName("BtnAdd")

# --- Draggable title bar ---
$titleBar.Add_MouseLeftButtonDown({
    $window.DragMove()
})

# --- Refresh UI ---
$script:isRefreshing = $false

function Refresh-TodoUI {
    if ($script:isRefreshing) { return }
    $script:isRefreshing = $true

    try {
        # Streak & greeting
        $txtStreak.Text = Get-StreakDisplay
        $txtGreeting.Text = Get-TimeGreeting

        # Quote or roast
        $streakInfo = Update-StreakFromTodos
        if ($streakInfo.IsBroken) {
            $txtQuote.Text = Get-GentleRoast
            $txtQuoteAuthor.Text = ""
        } else {
            $q = Get-MotivationalQuote
            $txtQuote.Text = $q.Text
            $txtQuoteAuthor.Text = "- $($q.Author)"
        }

        # Todo list
        $todoList.Children.Clear()
        $sections = Read-TodoSections
        $todayStr = (Get-Date).ToString("yyyy-MM-dd")
        $todaySection = $null

        foreach ($s in $sections) {
            if ($s.Date -eq $todayStr) {
                $todaySection = $s
                break
            }
        }

        if (-not $todaySection -or $todaySection.Items.Count -eq 0) {
            # Empty state
            $emptyBlock = [System.Windows.Controls.TextBlock]::new()
            $emptyBlock.Text = Get-EmptyStateMessage
            $emptyBlock.FontSize = 14
            $emptyBlock.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString($theme.Subtext0)
            $emptyBlock.HorizontalAlignment = "Center"
            $emptyBlock.Margin = [System.Windows.Thickness]::new(0, 20, 0, 20)
            $emptyBlock.TextWrapping = "Wrap"
            $todoList.Children.Add($emptyBlock) | Out-Null
        } else {
            for ($i = 0; $i -lt $todaySection.Items.Count; $i++) {
                $item = $todaySection.Items[$i]
                $itemIndex = $i
                $itemDate = $todayStr

                # Row container
                $row = [System.Windows.Controls.Grid]::new()
                $row.Margin = [System.Windows.Thickness]::new(4, 3, 4, 3)
                $col1 = [System.Windows.Controls.ColumnDefinition]::new()
                $col1.Width = [System.Windows.GridLength]::new(1, [System.Windows.GridUnitType]::Star)
                $col2 = [System.Windows.Controls.ColumnDefinition]::new()
                $col2.Width = [System.Windows.GridLength]::new(28)
                $row.ColumnDefinitions.Add($col1)
                $row.ColumnDefinitions.Add($col2)

                # Checkbox + text
                $cb = [System.Windows.Controls.CheckBox]::new()
                $cb.IsChecked = $item.Done
                $cb.Content = $item.Text
                $cb.FontSize = 14
                $cb.VerticalContentAlignment = "Center"
                $cb.Tag = @{ Date = $itemDate; Index = $itemIndex }

                $bc = [System.Windows.Media.BrushConverter]::new()
                if ($item.Done) {
                    $cb.Foreground = $bc.ConvertFromString($theme.Overlay0)
                    # Strikethrough via TextBlock
                    $tb = [System.Windows.Controls.TextBlock]::new()
                    $tb.Text = $item.Text
                    $tb.TextDecorations = [System.Windows.TextDecorations]::Strikethrough
                    $tb.Foreground = $bc.ConvertFromString($theme.Overlay0)
                    $cb.Content = $tb
                } else {
                    $cb.Foreground = $bc.ConvertFromString($theme.Text)
                }

                $cb.Add_Checked({
                    param($sender, $e)
                    $tag = $sender.Tag
                    Set-TodoItemDone -Date $tag.Date -Index $tag.Index -Done $true
                    Refresh-TodoUI
                })
                $cb.Add_Unchecked({
                    param($sender, $e)
                    $tag = $sender.Tag
                    Set-TodoItemDone -Date $tag.Date -Index $tag.Index -Done $false
                    Refresh-TodoUI
                })

                [System.Windows.Controls.Grid]::SetColumn($cb, 0)
                $row.Children.Add($cb) | Out-Null

                # Delete button (X in ASCII)
                $delBtn = [System.Windows.Controls.Button]::new()
                $delBtn.Content = "X"
                $delBtn.FontSize = 11
                $delBtn.Width = 24
                $delBtn.Height = 24
                $delBtn.Foreground = $bc.ConvertFromString($theme.Red)
                $delBtn.Background = [System.Windows.Media.Brushes]::Transparent
                $delBtn.BorderThickness = [System.Windows.Thickness]::new(0)
                $delBtn.Cursor = [System.Windows.Input.Cursors]::Hand
                $delBtn.Tag = @{ Date = $itemDate; Index = $itemIndex }
                $delBtn.ToolTip = "Delete"

                $delBtn.Add_Click({
                    param($sender, $e)
                    $tag = $sender.Tag
                    Remove-TodoItem -Date $tag.Date -Index $tag.Index
                    Refresh-TodoUI
                })

                [System.Windows.Controls.Grid]::SetColumn($delBtn, 1)
                $row.Children.Add($delBtn) | Out-Null

                $todoList.Children.Add($row) | Out-Null
            }
        }
    } finally {
        $script:isRefreshing = $false
    }
}

# --- Add todo ---
function Add-NewTodo {
    $text = $txtNewTodo.Text.Trim()
    if ($text -eq "") { return }
    Add-TodoItem -Text $text
    $txtNewTodo.Text = ""
    Refresh-TodoUI
    $txtNewTodo.Focus()
}

$btnAdd.Add_Click({ Add-NewTodo })
$txtNewTodo.Add_KeyDown({
    param($sender, $e)
    if ($e.Key -eq [System.Windows.Input.Key]::Return) {
        Add-NewTodo
        $e.Handled = $true
    }
})

# --- Placeholder text for input ---
$txtNewTodo.Text = ""
$txtNewTodo.Add_GotFocus({
    if ($txtNewTodo.Tag -eq "placeholder") {
        $txtNewTodo.Text = ""
        $txtNewTodo.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString($theme.Text)
        $txtNewTodo.Tag = $null
    }
})
$txtNewTodo.Add_LostFocus({
    if ($txtNewTodo.Text.Trim() -eq "") {
        $txtNewTodo.Text = "What needs to be done?"
        $txtNewTodo.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString($theme.Overlay0)
        $txtNewTodo.Tag = "placeholder"
    }
})

# Set initial placeholder
$txtNewTodo.Text = "What needs to be done?"
$txtNewTodo.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString($theme.Overlay0)
$txtNewTodo.Tag = "placeholder"

# --- FileSystemWatcher for live reload ---
$script:watcher = $null
$script:debounceTimer = $null

function Start-FileWatcher {
    $todoFile = Get-TodoFilePath
    $folder = Split-Path $todoFile -Parent
    $fileName = Split-Path $todoFile -Leaf

    if (-not (Test-Path $folder)) { return }

    $script:watcher = [System.IO.FileSystemWatcher]::new($folder, $fileName)
    $script:watcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite
    $script:watcher.EnableRaisingEvents = $true

    # Debounce timer (500ms)
    $script:debounceTimer = [System.Windows.Threading.DispatcherTimer]::new()
    $script:debounceTimer.Interval = [TimeSpan]::FromMilliseconds(500)
    $script:debounceTimer.Add_Tick({
        $script:debounceTimer.Stop()
        Refresh-TodoUI
    })

    Register-ObjectEvent -InputObject $script:watcher -EventName Changed -Action {
        $window.Dispatcher.Invoke({
            $script:debounceTimer.Stop()
            $script:debounceTimer.Start()
        })
    } | Out-Null
}

# --- Restore window position ---
$pos = Get-WindowPosition
if ($pos.Left -ge 0 -and $pos.Top -ge 0) {
    $window.Left = $pos.Left
    $window.Top = $pos.Top
    $window.WindowStartupLocation = "Manual"
} else {
    $window.WindowStartupLocation = "CenterScreen"
}

# --- Save position on move ---
$window.Add_LocationChanged({
    if ($window.Left -ge 0 -and $window.Top -ge 0) {
        Save-WindowPosition -Left $window.Left -Top $window.Top
    }
})

# --- Window events ---
$window.Add_Loaded({
    Refresh-TodoUI
    Start-FileWatcher
})

$window.Add_Closed({
    if ($script:watcher) {
        $script:watcher.EnableRaisingEvents = $false
        $script:watcher.Dispose()
    }
    if ($script:mutex) {
        $script:mutex.ReleaseMutex()
        $script:mutex.Dispose()
    }
    # Clean up PID file
    $pf = Join-Path $PSScriptRoot "widget.pid"
    if (Test-Path $pf) { Remove-Item $pf -Force -ErrorAction SilentlyContinue }
})

# --- Show window ---
$window.ShowDialog() | Out-Null
