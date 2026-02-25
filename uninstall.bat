@echo off
setlocal EnableDelayedExpansion
echo === Todo Widget Uninstaller ===
echo.

REM --- Parse persona argument ---
if "%~1"=="" goto :usage
if /i "%~1"=="ritesh" goto :set_ritesh
if /i "%~1"=="riya" goto :set_riya
goto :usage

:set_ritesh
set "PERSONA=ritesh"
set "SHORTCUT_NAME=Todo Widget"
set "PID_SUFFIX=-ritesh"
goto :start_uninstall

:set_riya
set "PERSONA=riya"
set "SHORTCUT_NAME=Riyas Todos"
set "PID_SUFFIX=-riya"
goto :start_uninstall

:start_uninstall
set "SCRIPT_DIR=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "PROFILE_DIR=%USERPROFILE%\Documents\WindowsPowerShell"
set "PROFILE=%PROFILE_DIR%\Microsoft.PowerShell_profile.ps1"

echo Uninstalling %PERSONA%'s widget...
echo.

REM --- [1/5] Kill running widget process ---
echo [1/5] Stopping widget process...
set "PID_FILE=%SCRIPT_DIR%widget%PID_SUFFIX%.pid"
if not exist "%PID_FILE%" goto :no_pid
set /p WIDGET_PID=<"%PID_FILE%"
taskkill /PID !WIDGET_PID! /F >nul 2>&1
if errorlevel 1 (
    echo   Process not running ^(stale PID^).
) else (
    echo   Killed process PID !WIDGET_PID!.
)
del /f "%PID_FILE%" >nul 2>&1
echo   Removed PID file.
goto :step2

:no_pid
echo   No PID file found ^(widget not running^).

REM --- [2/5] Remove startup shortcut ---
:step2
echo [2/5] Removing auto-start shortcut...
if exist "%STARTUP%\%SHORTCUT_NAME%.lnk" (
    del /f "%STARTUP%\%SHORTCUT_NAME%.lnk"
    echo   Deleted: Startup\%SHORTCUT_NAME%.lnk
) else (
    echo   Not found ^(already removed^).
)

REM --- [3/5] Remove PowerShell profile entry ---
echo [3/5] Cleaning PowerShell profile...
if not exist "%PROFILE%" goto :no_profile
findstr /C:"todo-cli.ps1" "%PROFILE%" >nul 2>&1
if errorlevel 1 goto :profile_clean
powershell -NoProfile -Command "(Get-Content '%PROFILE%') | Where-Object { $_ -notmatch 'todo-cli\.ps1' -and $_ -notmatch '# Todo Widget commands' } | Set-Content '%PROFILE%'"
echo   Removed todo-cli.ps1 from profile.
goto :step4

:profile_clean
echo   Not in profile ^(already clean^).
goto :step4

:no_profile
echo   No PowerShell profile found.

REM --- [4/5] Remove Task Scheduler task ---
:step4
echo [4/5] Removing scheduled task...
schtasks /Query /TN "TodoWidgetReminder" >nul 2>&1
if errorlevel 1 (
    echo   No scheduled task found.
) else (
    schtasks /Delete /TN "TodoWidgetReminder" /F >nul 2>&1
    echo   Deleted: TodoWidgetReminder task.
)

REM --- [5/5] Summary ---
echo [5/5] Done.
echo.
echo === Uninstall Complete ^(%PERSONA%^) ===
echo.
echo Removed:
echo   - Auto-start shortcut
echo   - PowerShell profile entry
echo   - Scheduled task ^(if any^)
echo   - Running widget process
echo.
echo Preserved:
echo   - Your todo data ^(todos.md, tracker.json, honey-pot.md^)
echo   - Project files in %SCRIPT_DIR%
echo.
pause
exit /b 0

:usage
echo Usage: uninstall.bat ^<persona^>
echo.
echo   uninstall.bat ritesh    Uninstall Ritesh's version
echo   uninstall.bat riya      Uninstall Riya's version
echo.
echo Data files ^(todos, tracker, honey pot^) are always preserved.
echo.
pause
exit /b 1
