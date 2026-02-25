@echo off
echo === Todo Widget Installer ===
echo.

REM --- Parse persona argument ---
if "%~1"=="" goto :usage
if /i "%~1"=="ritesh" goto :set_ritesh
if /i "%~1"=="riya" goto :set_riya
goto :usage

:set_ritesh
set "PERSONA=ritesh"
set "SHORTCUT_NAME=Todo Widget"
set "WIDGET_ARGS=\"%~dp0widget.pyw\""
set "PERSONA_INIT=init_folder(); print('  Folder:', get_widget_folder())"
set "CLI_CMDS=todo-up / todo-down / todo-restart"
goto :start_install

:set_riya
set "PERSONA=riya"
set "SHORTCUT_NAME=Riyas Todos"
set "WIDGET_ARGS=\"%~dp0widget.pyw\" --for-riya"
set "PERSONA_INIT=set_persona('riya'); init_folder(); print('  Folder:', get_widget_folder())"
set "CLI_CMDS=todo-riya-up / todo-riya-down / todo-riya-restart"
goto :start_install

:start_install
set "SCRIPT_DIR=%~dp0"

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)
echo [OK] Python found.

REM --- Install dependencies ---
echo.
echo [1/4] Installing Python dependencies...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if errorlevel 1 (
    echo WARNING: pip install had issues. Try running: pip install -r requirements.txt
)
echo Done.

REM --- Setup data folder ---
echo.
echo [2/4] Setting up data folder...
python -c "import sys; sys.path.insert(0, '%SCRIPT_DIR:\=/%'); from lib.markdown_io import init_folder, set_persona, get_widget_folder; %PERSONA_INIT%"
if errorlevel 1 (
    echo   ERROR: Failed to set up data folder.
    pause
    exit /b 1
)
echo Done.

REM --- Add to PowerShell profile ---
echo.
echo [3/4] Adding CLI commands to PowerShell profile...
set "PROFILE_DIR=%USERPROFILE%\Documents\WindowsPowerShell"
if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"
set "PROFILE=%PROFILE_DIR%\Microsoft.PowerShell_profile.ps1"

findstr /C:"todo-cli.ps1" "%PROFILE%" >nul 2>&1
if errorlevel 1 (
    echo.>> "%PROFILE%"
    echo # Todo Widget commands>> "%PROFILE%"
    echo . %SCRIPT_DIR%todo-cli.ps1>> "%PROFILE%"
    echo   Added to PowerShell profile.
) else (
    echo   Already in PowerShell profile.
)
echo Done.

REM --- Auto-start on Windows boot ---
echo.
echo [4/4] Setting up auto-start on boot...
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\%SHORTCUT_NAME%.lnk'); $s.TargetPath = 'pythonw.exe'; $s.Arguments = '%WIDGET_ARGS%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.WindowStyle = 7; $s.Save()"
echo   Created: Startup\%SHORTCUT_NAME%.lnk
echo Done.

echo.
echo === Installation Complete ^(%PERSONA%^) ===
echo.
echo You can now:
echo   - In PowerShell: %CLI_CMDS%
echo   - Widget will auto-start on Windows boot
echo.
echo To uninstall later: uninstall.bat %PERSONA%
echo.
pause
exit /b 0

:usage
echo Usage: install.bat ^<persona^>
echo.
echo   install.bat ritesh    Install Ritesh's version
echo   install.bat riya      Install Riya's version
echo.
pause
exit /b 1
