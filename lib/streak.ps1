# streak.ps1 - Streak calculation + tracker.json management

# Dot-source dependencies
. "$PSScriptRoot\markdown.ps1"

function Read-Tracker {
    $path = Get-TrackerFilePath
    if (-not (Test-Path $path)) {
        return @{
            currentStreak  = 0
            longestStreak  = 0
            lastActiveDate = $null
            lastReminder   = $null
            windowLeft     = -1
            windowTop      = -1
        }
    }
    $json = Read-FileWithRetry -Path $path
    return ($json | ConvertFrom-Json)
}

function Save-Tracker {
    param($Tracker)
    $path = Get-TrackerFilePath
    $json = $Tracker | ConvertTo-Json -Depth 5
    Write-FileWithRetry -Path $path -Content $json
}

function Update-StreakFromTodos {
    <#
    .SYNOPSIS
    Recalculates the streak by walking backward through todo sections.
    A day counts as "active" if it has at least one completed item.
    #>
    $sections = Read-TodoSections
    $tracker = Read-Tracker

    # Build a set of active dates (days with at least one completed item)
    $activeDates = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($s in $sections) {
        foreach ($item in $s.Items) {
            if ($item.Done) {
                [void]$activeDates.Add($s.Date)
                break
            }
        }
    }

    # Walk backward from today
    $streak = 0
    $date = Get-Date
    $today = $date.ToString("yyyy-MM-dd")

    # Check if today is active
    if ($activeDates.Contains($today)) {
        $streak = 1
        $date = $date.AddDays(-1)
    } else {
        # Today might not be done yet - check yesterday to see if streak is alive
        $yesterday = $date.AddDays(-1).ToString("yyyy-MM-dd")
        if ($activeDates.Contains($yesterday)) {
            # Streak is still alive (today just hasn't had completions yet)
            $streak = 0
            $date = $date.AddDays(-1)
        } else {
            # Streak is broken
            $tracker.currentStreak = 0
            if ($tracker.longestStreak -lt 0) { $tracker.longestStreak = 0 }
            $tracker.lastActiveDate = $null
            Save-Tracker -Tracker $tracker
            return @{
                CurrentStreak = 0
                LongestStreak = [int]$tracker.longestStreak
                IsBroken      = $true
                Milestone     = $null
            }
        }
    }

    # Count consecutive days backward
    while ($true) {
        $dateStr = $date.ToString("yyyy-MM-dd")
        if ($activeDates.Contains($dateStr)) {
            $streak++
            $date = $date.AddDays(-1)
        } else {
            break
        }
    }

    # Update tracker
    $tracker.currentStreak = $streak
    if ($streak -gt [int]$tracker.longestStreak) {
        $tracker.longestStreak = $streak
    }
    $tracker.lastActiveDate = $today
    Save-Tracker -Tracker $tracker

    # Check for milestone
    $milestone = $null
    . "$PSScriptRoot\quotes.ps1"
    $milestone = Get-StreakMilestoneMessage -Days $streak

    return @{
        CurrentStreak = $streak
        LongestStreak = [int]$tracker.longestStreak
        IsBroken      = $false
        Milestone     = $milestone
    }
}

function Get-StreakDisplay {
    <#
    .SYNOPSIS
    Returns a formatted string for the streak display.
    #>
    $info = Update-StreakFromTodos

    . "$PSScriptRoot\quotes.ps1"
    $emoji = Get-StreakEmoji -Days $info.CurrentStreak -IsBroken $info.IsBroken

    if ($info.IsBroken) {
        return "$emoji Streak broken - time for a comeback!"
    }

    if ($info.CurrentStreak -eq 0) {
        return "$emoji Complete a task to start your streak!"
    }

    $dayWord = if ($info.CurrentStreak -eq 1) { "Day" } else { "Day" }
    $text = "$emoji $($info.CurrentStreak) $dayWord Streak!"

    if ($info.Milestone) {
        $text += " $($info.Milestone)"
    }

    return $text
}

function Set-ReminderShown {
    $tracker = Read-Tracker
    $tracker.lastReminder = (Get-Date).ToString("yyyy-MM-dd")
    Save-Tracker -Tracker $tracker
}

function Test-ReminderShownToday {
    $tracker = Read-Tracker
    return ($tracker.lastReminder -eq (Get-Date).ToString("yyyy-MM-dd"))
}

function Save-WindowPosition {
    param([double]$Left, [double]$Top)
    $tracker = Read-Tracker
    $tracker.windowLeft = $Left
    $tracker.windowTop = $Top
    Save-Tracker -Tracker $tracker
}

function Get-WindowPosition {
    $tracker = Read-Tracker
    return @{
        Left = [double]$tracker.windowLeft
        Top  = [double]$tracker.windowTop
    }
}
