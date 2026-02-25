# todo-cli.ps1 - Registers todo-up, todo-down, todo-restart functions
# Source this in your PowerShell profile: . <path-to>\todo-cli.ps1

$script:TodoWidgetDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function todo-up {
    param([switch]$ForRiya)
    $suffix = if ($ForRiya) { "-riya" } else { "-ritesh" }
    $pidFile = Join-Path $script:TodoWidgetDir "widget$suffix.pid"

    # Check if already running
    if (Test-Path $pidFile) {
        $p = [int](Get-Content $pidFile -ErrorAction SilentlyContinue)
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            $label = if ($ForRiya) { "Riya's widget" } else { "Widget" }
            Write-Host "$label is already running (PID $p)." -ForegroundColor Yellow
            return
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    $widgetFile = Join-Path $script:TodoWidgetDir "widget.pyw"
    $args = "`"$widgetFile`""
    if ($ForRiya) { $args += " --for-riya" }
    Start-Process pythonw.exe -ArgumentList $args -WindowStyle Hidden

    $label = if ($ForRiya) { "Riya's widget" } else { "Widget" }
    Write-Host "$label launched." -ForegroundColor Green
}

function todo-down {
    param([switch]$ForRiya)
    $suffix = if ($ForRiya) { "-riya" } else { "-ritesh" }
    $pidFile = Join-Path $script:TodoWidgetDir "widget$suffix.pid"

    if (-not (Test-Path $pidFile)) {
        $label = if ($ForRiya) { "Riya's widget" } else { "Widget" }
        Write-Host "$label is not running." -ForegroundColor Yellow
        return
    }

    $widgetPid = [int](Get-Content $pidFile -ErrorAction SilentlyContinue)
    $proc = Get-Process -Id $widgetPid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $widgetPid -Force
        $label = if ($ForRiya) { "Riya's widget" } else { "Widget" }
        Write-Host "$label stopped (PID $widgetPid)." -ForegroundColor Green
    } else {
        Write-Host "Widget process not found (stale PID)." -ForegroundColor Yellow
    }

    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

function todo-restart {
    param([switch]$ForRiya)
    $label = if ($ForRiya) { "Riya's widget" } else { "Widget" }
    Write-Host "Restarting $label..." -ForegroundColor Cyan
    if ($ForRiya) {
        todo-down -ForRiya
        Start-Sleep -Milliseconds 500
        todo-up -ForRiya
    } else {
        todo-down
        Start-Sleep -Milliseconds 500
        todo-up
    }
}

# Convenience aliases for Riya's version
function todo-riya-up      { todo-up -ForRiya }
function todo-riya-down    { todo-down -ForRiya }
function todo-riya-restart { todo-restart -ForRiya }

Write-Host "Todo commands loaded: todo-up, todo-down, todo-restart, todo-riya-up, todo-riya-down, todo-riya-restart" -ForegroundColor DarkGray
