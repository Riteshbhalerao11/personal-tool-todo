# daily-todo-reminder.ps1
# Runs on login. If this is the first login today, reminds you to add a todo
# to Sticky Notes and opens the app.

$trackingFile = "$env:USERPROFILE\.todo-tracker"

# Get today's date as a simple string
$today = (Get-Date).ToString("yyyy-MM-dd")

# Check if we already reminded today
$alreadyReminded = $false
if (Test-Path $trackingFile) {
    $lastDate = (Get-Content $trackingFile -Tail 1).Trim()
    if ($lastDate -eq $today) {
        $alreadyReminded = $true
    }
}

if (-not $alreadyReminded) {
    # Record today so we don't remind again
    $today | Out-File -FilePath $trackingFile -Encoding utf8

    # Open Sticky Notes
    Start-Process "shell:AppsFolder\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App"

    # Show a toast notification
    Add-Type -AssemblyName System.Windows.Forms
    $balloon = New-Object System.Windows.Forms.NotifyIcon
    $balloon.Icon = [System.Drawing.SystemIcons]::Information
    $balloon.BalloonTipIcon = "Info"
    $balloon.BalloonTipTitle = "Daily Todo Reminder"
    $balloon.BalloonTipText = "Good morning! Don't forget to add your todos for today in Sticky Notes."
    $balloon.Visible = $true
    $balloon.ShowBalloonTip(10000)

    # Keep the icon visible long enough for the notification, then clean up
    Start-Sleep -Seconds 12
    $balloon.Dispose()
}
