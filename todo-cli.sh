# todo-cli.sh - registers todo-up / todo-down / todo-restart / todo-show shell functions.
# Source this from your ~/.bashrc:   source /path/to/todo-cli.sh
#
# Linux counterpart of todo-cli.ps1. Uses the same per-persona PID files
# (widget-<persona>.pid) that widget.pyw writes.

TODO_WIDGET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Prefer the install.sh-created venv (so system gi/WebKit + pip deps are visible),
# fall back to the system interpreter.
_todo_python() {
    if [ -x "$TODO_WIDGET_DIR/.venv/bin/python" ]; then
        echo "$TODO_WIDGET_DIR/.venv/bin/python"
    else
        echo "python3"
    fi
}

_todo_pidfile() { echo "$TODO_WIDGET_DIR/widget-${1:-ritesh}.pid"; }

_todo_running() {
    local f; f="$(_todo_pidfile "$1")"
    [ -f "$f" ] && kill -0 "$(cat "$f" 2>/dev/null)" 2>/dev/null
}

_todo_up() {
    local p="${1:-ritesh}" label="${2:-Widget}"
    if _todo_running "$p"; then
        echo "$label is already running (PID $(cat "$(_todo_pidfile "$p")"))."
        return
    fi
    rm -f "$(_todo_pidfile "$p")"
    local args=("$TODO_WIDGET_DIR/widget.pyw")
    [ "$p" = "riya" ] && args+=("--for-riya")
    nohup "$(_todo_python)" "${args[@]}" >/dev/null 2>&1 &
    echo "$label launched."
}

_todo_down() {
    local p="${1:-ritesh}" label="${2:-Widget}"
    local f; f="$(_todo_pidfile "$p")"
    if [ ! -f "$f" ]; then echo "$label is not running."; return; fi
    local pid; pid="$(cat "$f" 2>/dev/null)"
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        echo "$label stopped (PID $pid)."
    else
        echo "$label process not found (stale PID)."
    fi
    rm -f "$f"
}

# Raise/focus a running widget (SIGUSR2); launch it if not running.
# SIGUSR2 (not SIGUSR1) because WebKit/JSC uses SIGUSR1 for its GC.
_todo_show() {
    local p="${1:-ritesh}"
    if _todo_running "$p"; then
        kill -USR2 "$(cat "$(_todo_pidfile "$p")")" 2>/dev/null
    else
        _todo_up "$p" "Widget"
    fi
}

todo-up()      { _todo_up      ritesh "Widget"; }
todo-down()    { _todo_down    ritesh "Widget"; }
todo-restart() { _todo_down    ritesh "Widget"; sleep 0.5; _todo_up ritesh "Widget"; }
todo-show()    { _todo_show    ritesh; }

todo-riya-up()      { _todo_up   riya "Riya's widget"; }
todo-riya-down()    { _todo_down riya "Riya's widget"; }
todo-riya-restart() { _todo_down riya "Riya's widget"; sleep 0.5; _todo_up riya "Riya's widget"; }
todo-riya-show()    { _todo_show riya; }
