# markdown.ps1 - OneDrive detection + Markdown parser/writer

function Find-OneDrivePath {
    # 1. Try registry (most reliable for personal OneDrive)
    $regPaths = @(
        "HKCU:\Software\Microsoft\OneDrive\Accounts\Personal"
        "HKCU:\Software\Microsoft\OneDrive"
    )
    foreach ($rp in $regPaths) {
        try {
            $val = (Get-ItemProperty -Path $rp -Name "UserFolder" -ErrorAction SilentlyContinue).UserFolder
            if ($val -and (Test-Path $val)) { return $val }
        } catch {}
    }

    # 2. Try environment variables
    foreach ($envName in @("OneDrive", "OneDriveConsumer", "OneDriveCommercial")) {
        $val = [System.Environment]::GetEnvironmentVariable($envName)
        if ($val -and (Test-Path $val)) { return $val }
    }

    # 3. Common default paths
    $username = $env:USERNAME
    $commonPaths = @(
        "$env:USERPROFILE\OneDrive"
        "C:\Users\$username\OneDrive"
        "$env:USERPROFILE\OneDrive - Personal"
    )
    foreach ($p in $commonPaths) {
        if (Test-Path $p) { return $p }
    }

    return $null
}

function Get-TodoWidgetFolder {
    $oneDrive = Find-OneDrivePath
    if (-not $oneDrive) {
        # Fallback: use local AppData if OneDrive is not found
        $fallback = "$env:LOCALAPPDATA\TodoWidget"
        Write-Warning "OneDrive not found. Using fallback: $fallback"
        return $fallback
    }
    return Join-Path $oneDrive "TodoWidget"
}

function Get-TodoFilePath {
    return Join-Path (Get-TodoWidgetFolder) "todos.md"
}

function Get-TrackerFilePath {
    return Join-Path (Get-TodoWidgetFolder) "tracker.json"
}

function Initialize-TodoFolder {
    $folder = Get-TodoWidgetFolder
    if (-not (Test-Path $folder)) {
        New-Item -Path $folder -ItemType Directory -Force | Out-Null
    }

    $todoFile = Get-TodoFilePath
    if (-not (Test-Path $todoFile)) {
        Write-TodoFile -Sections @() -FilePath $todoFile
    }

    $trackerFile = Get-TrackerFilePath
    if (-not (Test-Path $trackerFile)) {
        $default = @{
            currentStreak  = 0
            longestStreak  = 0
            lastActiveDate = $null
            lastReminder   = $null
            windowLeft     = -1
            windowTop      = -1
        }
        $json = $default | ConvertTo-Json -Depth 5
        Write-FileWithRetry -Path $trackerFile -Content $json
    }
}

# --- File I/O with retry (handles OneDrive sync locks) ---

function Read-FileWithRetry {
    param(
        [string]$Path,
        [int]$MaxRetries = 3,
        [int]$DelayMs = 200
    )
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            $bytes = [System.IO.File]::ReadAllBytes($Path)
            return [System.Text.Encoding]::UTF8.GetString($bytes)
        } catch {
            if ($i -eq ($MaxRetries - 1)) { throw }
            Start-Sleep -Milliseconds $DelayMs
        }
    }
}

function Write-FileWithRetry {
    param(
        [string]$Path,
        [string]$Content,
        [int]$MaxRetries = 3,
        [int]$DelayMs = 200
    )
    # UTF-8 no BOM, LF line endings
    $Content = $Content -replace "`r`n", "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
            return
        } catch {
            if ($i -eq ($MaxRetries - 1)) { throw }
            Start-Sleep -Milliseconds $DelayMs
        }
    }
}

# --- Markdown Parsing ---

# Returns an array of section objects:
# @{ Date = "2026-02-25"; Items = @( @{ Text="Buy groceries"; Done=$false }, ... ) }
function Read-TodoSections {
    param([string]$FilePath = (Get-TodoFilePath))
    if (-not (Test-Path $FilePath)) { return @() }

    $raw = Read-FileWithRetry -Path $FilePath
    $lines = $raw -split "`n"

    $sections = [System.Collections.ArrayList]::new()
    $currentSection = $null

    foreach ($line in $lines) {
        $trimmed = $line.Trim()

        # Date header: ## 2026-02-25
        if ($trimmed -match '^##\s+(\d{4}-\d{2}-\d{2})') {
            if ($currentSection) { [void]$sections.Add($currentSection) }
            $currentSection = @{
                Date  = $Matches[1]
                Items = [System.Collections.ArrayList]::new()
            }
            continue
        }

        # Todo item: - [ ] or - [x]
        if ($currentSection -and $trimmed -match '^-\s+\[([ xX])\]\s+(.+)$') {
            $done = $Matches[1] -ne ' '
            $text = $Matches[2].Trim()
            [void]$currentSection.Items.Add(@{ Text = $text; Done = $done })
        }
    }

    if ($currentSection) { [void]$sections.Add($currentSection) }
    return $sections.ToArray()
}

function Get-TodaySection {
    param([array]$Sections)
    $today = (Get-Date).ToString("yyyy-MM-dd")
    foreach ($s in $Sections) {
        if ($s.Date -eq $today) { return $s }
    }
    return $null
}

# --- Markdown Writing ---

function Write-TodoFile {
    param(
        [array]$Sections,
        [string]$FilePath = (Get-TodoFilePath)
    )
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("# My Todos")
    [void]$sb.AppendLine("")

    foreach ($section in $Sections) {
        [void]$sb.AppendLine("## $($section.Date)")
        [void]$sb.AppendLine("")
        foreach ($item in $section.Items) {
            $check = if ($item.Done) { "x" } else { " " }
            [void]$sb.AppendLine("- [$check] $($item.Text)")
        }
        [void]$sb.AppendLine("")
    }

    $content = $sb.ToString().TrimEnd() + "`n"
    Write-FileWithRetry -Path $FilePath -Content $content
}

function Add-TodoItem {
    param(
        [string]$Text,
        [string]$FilePath = (Get-TodoFilePath)
    )
    $sections = Read-TodoSections -FilePath $FilePath
    $today = (Get-Date).ToString("yyyy-MM-dd")
    $todaySection = $null
    $todayIndex = -1

    for ($i = 0; $i -lt $sections.Count; $i++) {
        if ($sections[$i].Date -eq $today) {
            $todaySection = $sections[$i]
            $todayIndex = $i
            break
        }
    }

    if (-not $todaySection) {
        $todaySection = @{
            Date  = $today
            Items = [System.Collections.ArrayList]::new()
        }
        # Insert at beginning (most recent first)
        $newSections = [System.Collections.ArrayList]::new()
        [void]$newSections.Add($todaySection)
        foreach ($s in $sections) { [void]$newSections.Add($s) }
        $sections = $newSections.ToArray()
    }

    # Ensure Items is an ArrayList for adding
    if ($todaySection.Items -isnot [System.Collections.ArrayList]) {
        $al = [System.Collections.ArrayList]::new()
        foreach ($item in $todaySection.Items) { [void]$al.Add($item) }
        $todaySection.Items = $al
    }

    [void]$todaySection.Items.Add(@{ Text = $Text; Done = $false })
    Write-TodoFile -Sections $sections -FilePath $FilePath
}

function Set-TodoItemDone {
    param(
        [string]$Date,
        [int]$Index,
        [bool]$Done,
        [string]$FilePath = (Get-TodoFilePath)
    )
    $sections = Read-TodoSections -FilePath $FilePath
    foreach ($s in $sections) {
        if ($s.Date -eq $Date -and $Index -ge 0 -and $Index -lt $s.Items.Count) {
            $s.Items[$Index].Done = $Done
            break
        }
    }
    Write-TodoFile -Sections $sections -FilePath $FilePath
}

function Remove-TodoItem {
    param(
        [string]$Date,
        [int]$Index,
        [string]$FilePath = (Get-TodoFilePath)
    )
    $sections = Read-TodoSections -FilePath $FilePath
    foreach ($s in $sections) {
        if ($s.Date -eq $Date -and $Index -ge 0 -and $Index -lt $s.Items.Count) {
            if ($s.Items -isnot [System.Collections.ArrayList]) {
                $al = [System.Collections.ArrayList]::new()
                foreach ($item in $s.Items) { [void]$al.Add($item) }
                $s.Items = $al
            }
            $s.Items.RemoveAt($Index)
            break
        }
    }
    Write-TodoFile -Sections $sections -FilePath $FilePath
}
