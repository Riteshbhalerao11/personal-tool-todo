#!/usr/bin/env bash
# install.sh - Linux installer for the Todo Widget.
# Counterpart of install.bat (+ setup.ps1's auto-start).
#
# Usage:  ./install.sh ritesh    |    ./install.sh riya

set -u

echo "=== Todo Widget Installer (Linux) ==="
echo

# --- Parse persona argument ---
PERSONA="${1:-}"
case "$PERSONA" in
    ritesh)
        APP_NAME="Todo Widget"; WIDGET_ARGS=""; CLI_CMDS="todo-up / todo-down / todo-restart / todo-show" ;;
    riya)
        APP_NAME="Riyas Todos"; WIDGET_ARGS="--for-riya"; CLI_CMDS="todo-riya-up / todo-riya-down / todo-riya-restart / todo-riya-show" ;;
    *)
        echo "Usage: ./install.sh <persona>"
        echo
        echo "  ./install.sh ritesh    Install Ritesh's version"
        echo "  ./install.sh riya      Install Riya's version"
        exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
VENV_PY="$VENV/bin/python"

# --- Check Python ---
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi
echo "[OK] python3 found: $(python3 --version)"

# --- System packages (GTK/WebKit backend, tray, notifications) ---
echo
echo "[1/5] Checking system GUI packages..."
# Note: no python3-venv needed — uv creates the virtualenv itself.
APT_PKGS="python3-gi gir1.2-webkit2-4.1 gir1.2-ayatanaappindicator3-0.1 libnotify-bin"
if ! python3 -c "import gi; gi.require_version('WebKit2','4.1')" >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        echo "  Installing: $APT_PKGS"
        sudo apt-get install -y $APT_PKGS || \
            echo "  WARNING: apt install had issues; install these manually: $APT_PKGS"
    else
        echo "  Not on apt. Install the equivalents of: $APT_PKGS"
        echo "  (PyGObject + WebKit2GTK 4.1 + AppIndicator + libnotify)"
    fi
else
    echo "  GTK/WebKit2-4.1 backend already available."
fi

# --- Virtualenv via uv, with system site-packages (so it sees system gi/WebKit) ---
echo
echo "[2/5] Setting up Python environment (uv)..."
if ! command -v uv >/dev/null 2>&1; then
    echo "  uv not found — installing it..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || {
        echo "  ERROR: failed to install uv. Install it manually: https://docs.astral.sh/uv/"; exit 1; }
    export PATH="$HOME/.local/bin:$PATH"   # uv installs here
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "  ERROR: uv is not on PATH. Add ~/.local/bin to PATH and re-run."; exit 1
fi
echo "  uv: $(uv --version)"
if [ ! -x "$VENV_PY" ]; then
    uv venv --system-site-packages "$VENV" || { echo "  ERROR: 'uv venv' failed."; exit 1; }
fi
uv pip install --python "$VENV_PY" -r "$SCRIPT_DIR/requirements.txt" || \
    echo "  WARNING: 'uv pip install' had issues; check requirements.txt"
echo "  Done."

# --- Set up data folder ---
echo
echo "[3/5] Setting up data folder..."
"$VENV_PY" -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); \
from lib.markdown_io import init_folder, set_persona, get_widget_folder; \
set_persona('$PERSONA'); init_folder(); print('  Folder:', get_widget_folder())" || {
    echo "  ERROR: Failed to set up data folder."; exit 1; }

# --- Add CLI commands to ~/.bashrc ---
echo
echo "[4/5] Adding CLI commands to ~/.bashrc..."
BASHRC="$HOME/.bashrc"
if ! grep -q "todo-cli.sh" "$BASHRC" 2>/dev/null; then
    {
        echo ""
        echo "# Todo Widget commands"
        echo "source \"$SCRIPT_DIR/todo-cli.sh\""
    } >> "$BASHRC"
    echo "  Added to ~/.bashrc (run 'source ~/.bashrc' or open a new terminal)."
else
    echo "  Already in ~/.bashrc."
fi

# --- Auto-start on login (XDG autostart) ---
echo
echo "[5/5] Setting up auto-start on login..."
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
DESKTOP_FILE="$AUTOSTART_DIR/todo-widget-$PERSONA.desktop"
EXEC_CMD="$VENV_PY \"$SCRIPT_DIR/widget.pyw\""
[ -n "$WIDGET_ARGS" ] && EXEC_CMD="$EXEC_CMD $WIDGET_ARGS"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Daily todo sticky-note widget
Exec=$EXEC_CMD
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
EOF
echo "  Created: $DESKTOP_FILE"

echo
echo "=== Installation Complete ($PERSONA) ==="
echo
echo "You can now:"
echo "  - In a new terminal: $CLI_CMDS"
echo "  - Widget will auto-start on next login"
echo "  - (Optional) bind a key to 'todo-show' via GNOME Settings -> Keyboard -> Custom Shortcuts"
echo
echo "Start it now with:  source todo-cli.sh && todo-up"
echo "To uninstall later: ./uninstall.sh $PERSONA"
