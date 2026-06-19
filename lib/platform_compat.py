"""OS-specific compatibility layer for the Todo Widget.

All platform branching lives here. The Windows code paths are byte-for-byte
equivalent to the original inline implementation in ``widget.pyw`` (the Win32
``ctypes`` code was moved here verbatim), so Windows behaviour is unchanged.
Linux/macOS branches are added alongside.

Import-safe everywhere: ``ctypes.windll`` (which only exists on Windows) is only
ever touched inside ``IS_WINDOWS`` branches.
"""

import os
import sys
import subprocess

IS_WINDOWS = sys.platform.startswith('win')
IS_MAC = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes

# Win32 constants (plain ints, harmless to define everywhere).
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000


# --- Data directory -------------------------------------------------------

APP_DIR_NAME = 'TodoWidget'


def get_app_data_dir():
    """Per-user data directory for the todo files, tracker and honey pot.

    Windows: ``%LOCALAPPDATA%\\TodoWidget`` (unchanged from the original).
    macOS:   ``~/Library/Application Support/TodoWidget``.
    Linux:   ``$XDG_DATA_HOME/TodoWidget`` or ``~/.local/share/TodoWidget``.
    """
    if IS_WINDOWS:
        base = os.environ.get('LOCALAPPDATA', '.')
        return os.path.join(base, APP_DIR_NAME)
    if IS_MAC:
        return os.path.join(os.path.expanduser('~/Library/Application Support'), APP_DIR_NAME)
    base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, APP_DIR_NAME)


# --- Window handle (Windows only) -----------------------------------------

def find_hwnd_by_pid(pid):
    """Find the main visible window handle for a given PID. None off Windows."""
    if not IS_WINDOWS:
        return None
    user32 = ctypes.windll.user32
    result = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _):
        proc_id = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            result.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None


def hide_from_taskbar(hwnd):
    """Hide window from taskbar via WS_EX_TOOLWINDOW. No-op off Windows."""
    if not IS_WINDOWS or not hwnd:
        return
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    # Toggle visibility to apply
    user32.ShowWindow(hwnd, 0)  # SW_HIDE
    user32.ShowWindow(hwnd, 5)  # SW_SHOW


def apply_visual_tweaks(hwnd):
    """Apply DWM visual tweaks (border hiding, rounded corners) on Windows 11+.

    No-op off Windows (purely cosmetic).
    """
    if not IS_WINDOWS or not hwnd:
        return
    try:
        dwmapi = ctypes.windll.dwmapi

        # Hide the thin border line
        DWMWA_BORDER_COLOR = 34
        DWMWA_COLOR_NONE = 0xFFFFFFFE
        color = ctypes.c_uint(DWMWA_COLOR_NONE)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(color), ctypes.sizeof(color)
        )

        # Force rounded corners
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        corner_pref = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_pref), ctypes.sizeof(corner_pref)
        )
    except Exception:
        pass


# --- Confirmation dialog --------------------------------------------------

def confirm_dialog(window, title, message):
    """Native yes/no confirmation. Returns True only if explicitly confirmed.

    Windows: Win32 ``MessageBoxW`` (unchanged behaviour).
    Other:   pywebview's native confirmation dialog, with a JS ``confirm()``
             fallback. On any failure returns False so data is never destroyed
             silently.
    """
    if IS_WINDOWS:
        MB_YESNO = 0x04
        MB_ICONWARNING = 0x30
        IDYES = 6
        result = ctypes.windll.user32.MessageBoxW(
            0, message, title, MB_YESNO | MB_ICONWARNING
        )
        return result == IDYES

    # Non-Windows: pywebview marshals these onto the GUI thread internally.
    if window is not None and hasattr(window, 'create_confirmation_dialog'):
        try:
            return bool(window.create_confirmation_dialog(title, message))
        except Exception:
            pass
    if window is not None:
        try:
            return bool(window.evaluate_js('window.confirm({!r})'.format(message)))
        except Exception:
            pass
    return False


# --- Window geometry / opacity --------------------------------------------

def move_and_resize(hwnd, window, x, y, w, h):
    """Atomic move+resize. Windows uses SetWindowPos; others use pywebview."""
    if IS_WINDOWS and hwnd:
        SWP_NOZORDER = 0x0004
        ctypes.windll.user32.SetWindowPos(
            hwnd, None, int(x), int(y), int(w), int(h), SWP_NOZORDER
        )
    elif window is not None:
        window.move(int(x), int(y))
        window.resize(int(w), int(h))


def get_window_rect(hwnd):
    """Return the actual window rect {x, y, w, h} in physical pixels, or None."""
    if IS_WINDOWS and hwnd:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {
            'x': rect.left, 'y': rect.top,
            'w': rect.right - rect.left, 'h': rect.bottom - rect.top,
        }
    return None


def set_window_opacity(hwnd, window, pct):
    """Set window opacity 50-100%.

    Windows: layered-window alpha (unchanged behaviour).
    Linux/macOS: best-effort via the underlying GTK window; no-op on failure.
    """
    pct = max(50, min(100, int(pct)))
    if IS_WINDOWS:
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        WS_EX_LAYERED = 0x00080000
        LWA_ALPHA = 0x02
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if pct < 100:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            alpha = int(pct * 255 / 100)
            user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
        else:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        return
    # Best-effort on other platforms (pywebview's native GTK window).
    if window is None:
        return
    try:
        native = getattr(window, 'native', None)
        if native is not None and hasattr(native, 'set_opacity'):
            native.set_opacity(pct / 100.0)
    except Exception:
        pass


# --- Interactive move / resize (Linux/GTK) --------------------------------
#
# Wayland forbids a client from positioning its own toplevel, so the Win32-style
# absolute move/resize used on Windows does not work. Instead we ask the
# compositor to perform the move/resize via GTK's begin_move_drag /
# begin_resize_drag, which is the supported path on both Wayland and X11.

_GDK_EDGES = None


def _gtk_browserview(window):
    """Return the pywebview GTK BrowserView backing a pywebview window, or None."""
    if window is None:
        return None
    try:
        from webview.platforms.gtk import BrowserView
        return BrowserView.instances.get(window.uid)
    except Exception:
        return None


def start_window_move(window, x_root, y_root):
    """Begin a compositor-driven window move at screen coords (Linux/GTK).

    No-op on Windows/macOS, where pywebview's own drag region already works.
    """
    if not IS_LINUX:
        return
    bv = _gtk_browserview(window)
    if bv is None:
        return
    try:
        from gi.repository import Gdk, GLib

        def _begin():
            gdkwin = bv.window.get_window()
            if gdkwin is not None:
                gdkwin.begin_move_drag(1, int(x_root), int(y_root), Gdk.CURRENT_TIME)
            return False

        GLib.idle_add(_begin)
    except Exception:
        pass


def start_window_resize(window, edge, x_root, y_root):
    """Begin a compositor-driven resize from ``edge`` (e.g. 'se', 'n') (Linux/GTK).

    No-op on Windows/macOS.
    """
    if not IS_LINUX:
        return
    bv = _gtk_browserview(window)
    if bv is None:
        return
    try:
        from gi.repository import Gdk, GLib

        global _GDK_EDGES
        if _GDK_EDGES is None:
            _GDK_EDGES = {
                'nw': Gdk.WindowEdge.NORTH_WEST, 'n': Gdk.WindowEdge.NORTH,
                'ne': Gdk.WindowEdge.NORTH_EAST, 'w': Gdk.WindowEdge.WEST,
                'e': Gdk.WindowEdge.EAST, 'sw': Gdk.WindowEdge.SOUTH_WEST,
                's': Gdk.WindowEdge.SOUTH, 'se': Gdk.WindowEdge.SOUTH_EAST,
            }
        gdk_edge = _GDK_EDGES.get(edge)
        if gdk_edge is None:
            return

        def _begin():
            gdkwin = bv.window.get_window()
            if gdkwin is not None:
                gdkwin.begin_resize_drag(gdk_edge, 1, int(x_root), int(y_root), Gdk.CURRENT_TIME)
            return False

        GLib.idle_add(_begin)
    except Exception:
        pass


# --- Process spawning -----------------------------------------------------

def spawn_detached(args, cwd=None):
    """Launch a fully detached child process, portably."""
    if IS_WINDOWS:
        DETACHED_PROCESS = 0x00000008
        return subprocess.Popen(args, creationflags=DETACHED_PROCESS,
                                close_fds=True, cwd=cwd)
    # POSIX: start_new_session (setsid) detaches from the controlling session,
    # so the child survives the parent's window.destroy().
    return subprocess.Popen(args, start_new_session=True, close_fds=True, cwd=cwd)


# --- Desktop persistence (keep widget visible like a sticky note) ----------

def start_desktop_persist(api_obj, window):
    """Start the Win+D / Show-Desktop restore loop on Windows; no-op elsewhere.

    Returns the started Thread, or None when not applicable. There is no
    Win+D equivalent on Linux/macOS, so the widget simply behaves as a normal
    desktop window there.
    """
    if not IS_WINDOWS:
        return None
    import threading
    t = threading.Thread(target=_desktop_persist_loop,
                         args=(api_obj, window), daemon=True)
    t.start()
    return t


def _desktop_persist_loop(api_obj, window):
    import time
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    time.sleep(2)  # wait for hwnd to be cached

    while True:
        time.sleep(0.5)
        hwnd = api_obj._hwnd
        if not hwnd:
            continue
        # Skip if user explicitly minimized to tray
        if api_obj._honey_pot_mode:
            continue
        try:
            if not user32.IsWindowVisible(hwnd) and not getattr(api_obj, '_tray_hidden', False):
                # Window was hidden (e.g. Show Desktop) — restore it
                user32.ShowWindow(hwnd, SW_RESTORE)
            elif user32.IsIconic(hwnd):
                # Window was minimized — restore it
                user32.ShowWindow(hwnd, SW_RESTORE)
        except Exception:
            pass


# --- Global "show the widget" trigger -------------------------------------

def start_show_listener(on_show):
    """Register a global 'show/focus the widget' trigger.

    Windows: global Alt+T hotkey via RegisterHotKey (unchanged behaviour).
    Linux/macOS: listen for SIGUSR2 (sent by ``todo-cli.sh show`` / a custom
                 GNOME keyboard shortcut) and raise the window. This avoids a
                 fragile global key-grab that does not work reliably on Wayland.
                 SIGUSR2 (not SIGUSR1) is used because WebKit/JSC claims SIGUSR1
                 for its garbage collector.

    Returns the started thread / handle, or None when unavailable.
    """
    if IS_WINDOWS:
        import threading
        t = threading.Thread(target=_win_hotkey_loop, args=(on_show,), daemon=True)
        t.start()
        return t

    # POSIX: respond to SIGUSR2 via the GLib main loop (reliable with GTK).
    try:
        import signal
        from gi.repository import GLib
    except Exception:
        return None
    try:
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2,
                             _glib_signal_cb, on_show)
        return True
    except Exception:
        return None


def _glib_signal_cb(on_show):
    try:
        on_show()
    except Exception:
        pass
    return True  # keep the signal source installed


def raise_to_foreground(hwnd):
    """Bring the window to the foreground (Windows). No-op elsewhere."""
    if IS_WINDOWS and hwnd:
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def _win_hotkey_loop(on_show):
    user32 = ctypes.windll.user32
    MOD_ALT = 0x0001
    VK_T = 0x54
    HOTKEY_ID = 1
    WM_HOTKEY = 0x0312

    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT, VK_T):
        return  # another instance may have registered it

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            on_show()


# --- Notifications --------------------------------------------------------

def notify(title, message):
    """Best-effort desktop notification when no tray icon is available."""
    try:
        if IS_LINUX:
            from shutil import which
            if which('notify-send'):
                subprocess.Popen(['notify-send', '-a', 'TodoWidget', title, message])
                return True
    except Exception:
        pass
    return False
