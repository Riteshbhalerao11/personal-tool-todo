#!/usr/bin/env bash
# uninstall.sh - reverses install.sh. User data (todos/tracker/honey-pot) is preserved.
# Counterpart of uninstall.bat.
#
# Usage:  ./uninstall.sh ritesh    |    ./uninstall.sh riya

set -u

echo "=== Todo Widget Uninstaller (Linux) ==="
echo

PERSONA="${1:-}"
case "$PERSONA" in
    ritesh|riya) ;;
    *)
        echo "Usage: ./uninstall.sh <persona>   (ritesh | riya)"
        exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Stop running widget via PID file ---
echo "[1/3] Stopping widget..."
PID_FILE="$SCRIPT_DIR/widget-$PERSONA.pid"
if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null)"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null && echo "  Stopped (PID $PID)."
    fi
    rm -f "$PID_FILE"
else
    echo "  Not running."
fi

# --- Remove autostart entry ---
echo
echo "[2/3] Removing auto-start entry..."
DESKTOP_FILE="$HOME/.config/autostart/todo-widget-$PERSONA.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo "  Removed: $DESKTOP_FILE"
else
    echo "  No autostart entry found."
fi

# --- Remove CLI source line from ~/.bashrc (only if no other persona installed) ---
echo
echo "[3/3] Cleaning up ~/.bashrc..."
OTHER="ritesh"; [ "$PERSONA" = "ritesh" ] && OTHER="riya"
if [ -f "$HOME/.config/autostart/todo-widget-$OTHER.desktop" ]; then
    echo "  Other persona ($OTHER) still installed; leaving CLI commands in ~/.bashrc."
else
    BASHRC="$HOME/.bashrc"
    if grep -q "todo-cli.sh" "$BASHRC" 2>/dev/null; then
        # Drop the "# Todo Widget commands" comment and the source line.
        grep -v "todo-cli.sh" "$BASHRC" | grep -v "^# Todo Widget commands$" > "$BASHRC.tmp" \
            && mv "$BASHRC.tmp" "$BASHRC"
        echo "  Removed CLI commands from ~/.bashrc."
    else
        echo "  Nothing to remove."
    fi
fi

echo
echo "=== Uninstall Complete ($PERSONA) ==="
echo "Your data is preserved. The .venv/ folder was left intact (shared)."
echo "Remove it manually with:  rm -rf \"$SCRIPT_DIR/.venv\""
