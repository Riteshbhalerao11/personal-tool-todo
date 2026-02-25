# setup.ps1 - One-time Task Scheduler + OneDrive folder setup

#Requires -RunAsAdministrator

Add-Type -AssemblyName PresentationFramework

$libDir = Join-Path $PSScriptRoot "lib"
. "$libDir\markdown.ps1"

Write-Host "=== Todo Widget Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Initialize OneDrive folder + data files ---
Write-Host "[1/3] Setting up data folder..." -ForegroundColor Yellow

$folder = Get-TodoWidgetFolder
$oneDrive = Find-OneDrivePath
if ($oneDrive) {
    Write-Host "  OneDrive found: $oneDrive" -ForegroundColor Green
} else {
    Write-Host "  OneDrive not found - using local fallback: $folder" -ForegroundColor DarkYellow
}

Initialize-TodoFolder
Write-Host "  Data folder: $folder" -ForegroundColor Green
Write-Host "  todos.md:    $(Get-TodoFilePath)" -ForegroundColor Green
Write-Host "  tracker.json: $(Get-TrackerFilePath)" -ForegroundColor Green
Write-Host ""

# --- 2. Register Task Scheduler task for reminder at login ---
Write-Host "[2/3] Registering login reminder task..." -ForegroundColor Yellow

$taskName = "TodoWidgetReminder"
$reminderScript = Join-Path $PSScriptRoot "reminder.ps1"

# Remove old task if it exists
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Also remove legacy task if present
try {
    Unregister-ScheduledTask -TaskName "DailyTodoReminder" -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$reminderScript`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Shows Todo Widget reminder popup at login" `
    -Force | Out-Null

Write-Host "  Scheduled task '$taskName' registered for user $env:USERNAME" -ForegroundColor Green
Write-Host ""

# --- 3. Clean up old script if present ---
Write-Host "[3/3] Cleaning up..." -ForegroundColor Yellow

$oldScript = Join-Path $PSScriptRoot "daily-todo-reminder.ps1"
if (Test-Path $oldScript) {
    Remove-Item $oldScript -Force
    Write-Host "  Removed old daily-todo-reminder.ps1" -ForegroundColor Green
} else {
    Write-Host "  No old scripts to clean up" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now:" -ForegroundColor White
Write-Host "  - Run widget.ps1 to launch the todo widget" -ForegroundColor White
Write-Host "  - The reminder popup will show at each login" -ForegroundColor White
Write-Host "  - Edit todos.md from any device via OneDrive" -ForegroundColor White
Write-Host ""

# Offer to launch widget now
$result = [System.Windows.MessageBox]::Show(
    "Setup complete! Would you like to launch the Todo Widget now?",
    "Todo Widget Setup",
    [System.Windows.MessageBoxButton]::YesNo,
    [System.Windows.MessageBoxImage]::Question
)

if ($result -eq [System.Windows.MessageBoxResult]::Yes) {
    $widgetPath = Join-Path $PSScriptRoot "widget.ps1"
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$widgetPath`""
}
