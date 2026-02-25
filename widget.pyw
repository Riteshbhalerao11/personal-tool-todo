"""Todo Widget - main entry point (pywebview + HTML UI + system tray)."""

import os
import sys
import subprocess
import threading
import time
import ctypes
import ctypes.wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview
from PIL import Image, ImageDraw
import pystray

from lib.markdown_io import (
    init_folder, get_todo_path, get_today_items, add_todo_item,
    set_todo_done, remove_todo_item, update_todo_text, set_todo_depth,
    reorder_todo_item, insert_todo_item,
    clear_today_items, read_tracker, save_tracker, get_today_str,
    set_persona, get_persona, get_honey_pot_path,
    read_honey_pot_messages, add_honey_pot_message, update_honey_pot_message,
    remove_honey_pot_message, clear_honey_pot_messages,
    read_todo_sections, write_todo_file, write_honey_pot_file,
)
from lib.streak import update_streak, get_streak_display
from lib.quotes import get_daily_quote, get_time_greeting, get_poem_of_day

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


FIREBASE_URL = 'https://todo-app-acd7b-default-rtdb.firebaseio.com'

# Win32 constants
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000


def find_hwnd_by_pid(pid):
    """Find the main visible window handle for a given PID."""
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
    """Use Win32 API to hide window from taskbar by setting WS_EX_TOOLWINDOW."""
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    # Toggle visibility to apply
    user32.ShowWindow(hwnd, 0)  # SW_HIDE
    user32.ShowWindow(hwnd, 5)  # SW_SHOW


def apply_dwm_tweaks(hwnd):
    """Apply DWM visual tweaks (border hiding, rounded corners) on Windows 11+."""
    if not hwnd:
        return
    # DWM tweaks (Windows 11+)
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


class Api:
    def __init__(self, persona='ritesh'):
        self._window = None
        self._hwnd = None
        self._last_mtime = 0
        self._last_honey_mtime = 0
        self._suppress_watch = False
        self._suppress_fb_listen = False
        self._persona = persona
        self._honey_pot_mode = False

        # Firebase setup (None if not configured)
        self._firebase = None
        if FIREBASE_URL:
            from lib.firebase_sync import FirebaseSync
            self._firebase = FirebaseSync(FIREBASE_URL, persona)

    def set_window(self, window):
        self._window = window

    def get_initial_data(self):
        init_folder()
        items = get_today_items()
        streak = update_streak()
        greeting = get_time_greeting()
        quote = get_daily_quote()
        tracker = read_tracker()

        return {
            'items': items,
            'date': get_today_str(),
            'streak': streak,
            'streak_display': get_streak_display(),
            'greeting': greeting,
            'quote': quote,
            'uiFontSize': tracker.get('uiFontSize', 14),
            'todoFontSize': tracker.get('todoFontSize', 15),
            'persona': self._persona,
        }

    def _update_mtime(self):
        """Update cached mtime so file watcher ignores our own writes."""
        try:
            self._last_mtime = os.path.getmtime(get_todo_path())
        except OSError:
            pass

    def add_todo(self, text):
        add_todo_item(text)
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def add_todo_at_depth(self, text, depth):
        add_todo_item(text, depth=max(0, min(3, int(depth))))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def toggle_todo(self, index, done):
        set_todo_done(get_today_str(), index, done)
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def delete_todo(self, index):
        remove_todo_item(get_today_str(), index)
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def update_todo_text(self, index, text):
        update_todo_text(get_today_str(), index, text)
        self._update_mtime()
        self._sync_todos()

    def confirm_and_clear_todos(self):
        # Native Windows message box (appears as a proper OS dialog)
        MB_YESNO = 0x04
        MB_ICONWARNING = 0x30
        IDYES = 6
        result = ctypes.windll.user32.MessageBoxW(
            0, "Clear all todos for today? This cannot be undone.",
            "Clear All", MB_YESNO | MB_ICONWARNING
        )
        if result != IDYES:
            return None
        clear_today_items(get_today_str())
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def set_todo_depth(self, index, depth):
        set_todo_depth(get_today_str(), index, depth)
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def reorder_todo(self, from_index, to_index):
        reorder_todo_item(get_today_str(), int(from_index), int(to_index))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def insert_todo_after(self, index, text, depth):
        insert_todo_item(get_today_str(), int(index), str(text).strip(), max(0, min(3, int(depth))))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def open_url(self, url):
        """Open a URL in the default system browser."""
        import webbrowser
        webbrowser.open(url)

    def get_poem_of_day(self):
        """Return today's poem (cached for the day)."""
        return get_poem_of_day()

    def get_streak_data(self):
        return {
            'info': update_streak(),
            'display': get_streak_display(),
        }

    def set_ui_font_size(self, size):
        tracker = read_tracker()
        tracker['uiFontSize'] = size
        save_tracker(tracker)

    def set_todo_font_size(self, size):
        tracker = read_tracker()
        tracker['todoFontSize'] = size
        save_tracker(tracker)

    def save_position(self, x, y, w, h):
        tracker = read_tracker()
        tracker['windowLeft'] = x
        tracker['windowTop'] = y
        tracker['windowWidth'] = w
        tracker['windowHeight'] = h
        save_tracker(tracker)

    def minimize_to_tray(self):
        """Hide window to system tray."""
        if self._window:
            self._window.hide()

    def get_window_rect(self):
        """Return the actual Win32 window rect {x, y, w, h} in physical pixels."""
        if self._hwnd:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
            return {
                'x': rect.left, 'y': rect.top,
                'w': rect.right - rect.left, 'h': rect.bottom - rect.top,
            }
        return None

    def resize_window(self, w, h):
        """Called from JS drag-resize handler."""
        if self._window:
            self._window.resize(int(w), int(h))

    def move_and_resize(self, x, y, w, h):
        """Atomic move+resize using SetWindowPos to avoid flicker."""
        hwnd = getattr(self, '_hwnd', None)
        if hwnd:
            SWP_NOZORDER = 0x0004
            ctypes.windll.user32.SetWindowPos(
                hwnd, None, int(x), int(y), int(w), int(h), SWP_NOZORDER
            )
        elif self._window:
            self._window.move(int(x), int(y))
            self._window.resize(int(w), int(h))

    # --- Honey Pot ---

    def get_honey_pot_messages(self):
        return read_honey_pot_messages()

    def _update_honey_mtime(self):
        try:
            self._last_honey_mtime = os.path.getmtime(get_honey_pot_path())
        except OSError:
            pass

    def add_honey_pot_msg(self, text):
        add_honey_pot_message(text, self._persona)
        self._update_honey_mtime()
        self._sync_honeypot()
        return read_honey_pot_messages()

    def update_honey_pot_msg(self, index, text):
        update_honey_pot_message(index, text)
        self._update_honey_mtime()
        self._sync_honeypot()

    def delete_honey_pot_msg(self, index):
        remove_honey_pot_message(index)
        self._update_honey_mtime()
        self._sync_honeypot()
        return read_honey_pot_messages()

    def confirm_and_clear_honey_pot(self):
        MB_YESNO = 0x04
        MB_ICONWARNING = 0x30
        IDYES = 6
        result = ctypes.windll.user32.MessageBoxW(
            0, "Clear all honey pot messages? This cannot be undone.",
            "Clear Honey Pot", MB_YESNO | MB_ICONWARNING
        )
        if result != IDYES:
            return None
        clear_honey_pot_messages()
        self._update_honey_mtime()
        self._sync_honeypot()
        return read_honey_pot_messages()

    def set_honey_pot_mode(self, active):
        self._honey_pot_mode = active
        return active

    # --- Firebase Sync Helpers ---

    def _sync_todos(self):
        """Push current todo sections to Firebase (background thread)."""
        if not self._firebase:
            return
        def _push():
            try:
                today = get_today_str()
                items = get_today_items()
                self._suppress_fb_listen = True
                self._firebase.push_today_todos(today, items)
                time.sleep(1)
                self._suppress_fb_listen = False
            except Exception:
                self._suppress_fb_listen = False
        threading.Thread(target=_push, daemon=True).start()

    def _sync_honeypot(self):
        """Push honeypot messages to Firebase (background thread)."""
        if not self._firebase:
            return
        def _push():
            try:
                messages = read_honey_pot_messages()
                self._suppress_fb_listen = True
                self._firebase.push_honeypot(messages)
                time.sleep(1)
                self._suppress_fb_listen = False
            except Exception:
                self._suppress_fb_listen = False
        threading.Thread(target=_push, daemon=True).start()

    def _sync_tracker(self):
        """Push tracker data to Firebase (background thread)."""
        if not self._firebase:
            return
        def _push():
            try:
                tracker = read_tracker()
                self._firebase.push_tracker(tracker)
            except Exception:
                pass
        threading.Thread(target=_push, daemon=True).start()

    def _start_firebase_listeners(self):
        """Start SSE listeners for real-time updates from Firebase."""
        if not self._firebase:
            return

        # Listen for our own persona's todo path — changes from
        # the other machine (same persona) arrive here.
        def on_todo_change(event_data):
            if self._suppress_fb_listen:
                return
            try:
                # event_data is {'path': '...', 'data': ...}
                # Re-fetch the full today section from Firebase
                today = get_today_str()
                fb_items = self._firebase.read(f"todos/{self._persona}/{today}/items")
                if fb_items is None:
                    return
                if not isinstance(fb_items, list):
                    return

                # Convert to local format and write to file
                items = []
                for item in fb_items:
                    if isinstance(item, dict):
                        items.append({
                            'text': item.get('text', ''),
                            'done': item.get('done', False),
                            'depth': item.get('depth', 0),
                        })

                # Update local file
                sections = read_todo_sections()
                found = False
                for s in sections:
                    if s['date'] == today:
                        s['items'] = items
                        found = True
                        break
                if not found:
                    sections.insert(0, {'date': today, 'items': items})

                self._suppress_watch = True
                write_todo_file(sections)
                self._last_mtime = os.path.getmtime(get_todo_path())
                self._suppress_watch = False

                if self._window and not self._honey_pot_mode:
                    self._window.evaluate_js('refreshFromFile()')
            except Exception:
                self._suppress_watch = False

        # Listen for honeypot changes
        def on_honeypot_change(event_data):
            if self._suppress_fb_listen:
                return
            try:
                fb_messages = self._firebase.read("honeypot/messages")
                if fb_messages is None:
                    return
                if not isinstance(fb_messages, list):
                    return

                messages = []
                for msg in fb_messages:
                    if isinstance(msg, dict):
                        messages.append({
                            'text': msg.get('text', ''),
                            'from': msg.get('from', ''),
                            'date': msg.get('date', ''),
                        })

                self._suppress_watch = True
                write_honey_pot_file(messages)
                self._last_honey_mtime = os.path.getmtime(get_honey_pot_path())
                self._suppress_watch = False

                if self._window and self._honey_pot_mode:
                    self._window.evaluate_js('refreshHoneyPot()')
            except Exception:
                self._suppress_watch = False

        self._firebase.listen(f"todos/{self._persona}", on_todo_change)
        self._firebase.listen("honeypot", on_honeypot_change)

    def _initial_firebase_sync(self):
        """On startup, pull latest data from Firebase if available."""
        if not self._firebase:
            return
        def _pull():
            try:
                today = get_today_str()
                fb_items = self._firebase.read(f"todos/{self._persona}/{today}/items")
                if fb_items and isinstance(fb_items, list):
                    items = []
                    for item in fb_items:
                        if isinstance(item, dict):
                            items.append({
                                'text': item.get('text', ''),
                                'done': item.get('done', False),
                                'depth': item.get('depth', 0),
                            })

                    sections = read_todo_sections()
                    found = False
                    for s in sections:
                        if s['date'] == today:
                            # Only overwrite if Firebase has data and local is empty
                            if not s['items'] and items:
                                s['items'] = items
                                found = True
                            else:
                                found = True
                            break
                    if not found and items:
                        sections.insert(0, {'date': today, 'items': items})

                    if not found or items:
                        self._suppress_watch = True
                        write_todo_file(sections)
                        self._last_mtime = os.path.getmtime(get_todo_path())
                        self._suppress_watch = False

                        if self._window and not self._honey_pot_mode:
                            self._window.evaluate_js('refreshFromFile()')
            except Exception:
                self._suppress_watch = False

            # Also push current local state to Firebase (in case we have newer data)
            try:
                today = get_today_str()
                items = get_today_items()
                if items:
                    self._suppress_fb_listen = True
                    self._firebase.push_today_todos(today, items)
                    time.sleep(1)
                    self._suppress_fb_listen = False
            except Exception:
                self._suppress_fb_listen = False

            try:
                messages = read_honey_pot_messages()
                if messages:
                    self._suppress_fb_listen = True
                    self._firebase.push_honeypot(messages)
                    time.sleep(1)
                    self._suppress_fb_listen = False
            except Exception:
                self._suppress_fb_listen = False

        threading.Thread(target=_pull, daemon=True).start()

    # --- Settings ---

    SETTINGS_DEFAULTS = {
        'remindersEnabled': True,
        'reminderInterval': 60,
        'windowOpacity': 100,
    }

    SETTINGS_WHITELIST = set(SETTINGS_DEFAULTS.keys())

    def get_settings(self):
        tracker = read_tracker()
        result = {}
        for key, default in self.SETTINGS_DEFAULTS.items():
            result[key] = tracker.get(key, default)
        return result

    def update_setting(self, key, value):
        if key not in self.SETTINGS_WHITELIST:
            return False
        tracker = read_tracker()
        tracker[key] = value
        save_tracker(tracker)
        return True

    def reset_settings(self):
        tracker = read_tracker()
        for key, default in self.SETTINGS_DEFAULTS.items():
            tracker[key] = default
        tracker['uiFontSize'] = 14
        tracker['todoFontSize'] = 15
        save_tracker(tracker)
        # Apply defaults immediately
        self.set_window_opacity(100)
        return self.SETTINGS_DEFAULTS

    def set_window_opacity(self, pct):
        """Set window opacity 50-100% using Win32 SetLayeredWindowAttributes."""
        pct = max(50, min(100, int(pct)))
        if not self._hwnd:
            return
        user32 = ctypes.windll.user32
        WS_EX_LAYERED = 0x00080000
        LWA_ALPHA = 0x02
        style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        if pct < 100:
            user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            alpha = int(pct * 255 / 100)
            user32.SetLayeredWindowAttributes(self._hwnd, 0, alpha, LWA_ALPHA)
        else:
            user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)

    def restart_widget(self):
        """Relaunch widget as a detached process, then close this one."""
        args = [sys.executable, os.path.join(BASE_DIR, 'widget.pyw')]
        if self._persona == 'riya':
            args.append('--for-riya')
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(args, creationflags=DETACHED_PROCESS, close_fds=True)
        if self._window:
            self._window.destroy()

    def close_widget(self):
        if self._window:
            self._window.destroy()


REMINDER_MESSAGES = [
    "You haven't added any todos today! Don't let the day slip away.",
    "No todos yet today - what are you working on?",
    "Your sticky note is empty today. Time to plan!",
    "Zero todos today? Even one small task counts!",
    "Hey! Your todo list is lonely today. Add something!",
]


def reminder_loop(api_obj, tray_icon_ref):
    """Background thread: configurable reminders 24/7 when today's list is empty."""
    import random
    from datetime import datetime

    time.sleep(60)  # wait 1 min after startup before first check

    while True:
        try:
            # Skip reminders in honey pot mode
            if not api_obj._honey_pot_mode:
                tracker = read_tracker()
                enabled = tracker.get('remindersEnabled', True)
                interval_min = tracker.get('reminderInterval', 60)

                if enabled:
                    items = get_today_items()
                    has_todos = len(items) > 0

                    if not has_todos:
                        now = datetime.now()
                        last_str = tracker.get('lastReminderTime')
                        should_notify = True

                        if last_str:
                            try:
                                last_time = datetime.fromisoformat(last_str)
                                elapsed = (now - last_time).total_seconds()
                                should_notify = elapsed >= interval_min * 60
                            except (ValueError, TypeError):
                                pass

                        if should_notify:
                            icon = tray_icon_ref.get('icon')
                            if icon:
                                msg = random.choice(REMINDER_MESSAGES)
                                icon.notify(msg, 'Todo Reminder')
                            tracker['lastReminderTime'] = now.isoformat()
                            save_tracker(tracker)
        except Exception:
            pass

        time.sleep(300)  # poll every 5 minutes


def file_watcher(api_obj, window):
    path = get_todo_path()
    honey_path = get_honey_pot_path()
    try:
        api_obj._last_mtime = os.path.getmtime(path)
    except OSError:
        api_obj._last_mtime = 0
    try:
        api_obj._last_honey_mtime = os.path.getmtime(honey_path)
    except OSError:
        api_obj._last_honey_mtime = 0

    while True:
        time.sleep(2)
        if api_obj._suppress_watch:
            continue
        try:
            mtime = os.path.getmtime(path)
            if mtime != api_obj._last_mtime:
                api_obj._last_mtime = mtime
                if not api_obj._honey_pot_mode:
                    window.evaluate_js('refreshFromFile()')
        except Exception:
            pass
        try:
            honey_mtime = os.path.getmtime(honey_path)
            if honey_mtime != api_obj._last_honey_mtime:
                api_obj._last_honey_mtime = honey_mtime
                if api_obj._honey_pot_mode:
                    window.evaluate_js('refreshHoneyPot()')
        except Exception:
            pass


def create_tray_icon(persona='ritesh'):
    if persona == 'riya':
        img = Image.new('RGBA', (64, 64), (255, 200, 220, 255))
        draw = ImageDraw.Draw(img)
        # Draw a simple heart shape
        draw.polygon(
            [(32, 52), (8, 28), (8, 18), (16, 10), (24, 10), (32, 20),
             (40, 10), (48, 10), (56, 18), (56, 28)],
            fill=(220, 60, 100, 255)
        )
        draw.rectangle([(2, 2), (61, 61)], outline=(200, 150, 170, 255), width=2)
    else:
        img = Image.new('RGBA', (64, 64), (255, 248, 181, 255))
        draw = ImageDraw.Draw(img)
        draw.line([(18, 34), (28, 44), (46, 20)], fill=(74, 124, 63, 255), width=6)
        draw.rectangle([(2, 2), (61, 61)], outline=(180, 160, 100, 255), width=2)
    return img


def main():
    persona = 'riya' if '--for-riya' in sys.argv else 'ritesh'
    set_persona(persona)

    init_folder()
    api_obj = Api(persona)

    tracker = read_tracker()
    x = tracker.get('windowLeft', -1)
    y = tracker.get('windowTop', -1)
    w = tracker.get('windowWidth', 380)
    h = tracker.get('windowHeight', 520)

    ui_dir = os.path.join(BASE_DIR, 'ui')

    if persona == 'riya':
        window_title = "Riya's Todos"
        bg_color = '#FFE4EC'
    else:
        window_title = 'Todo Widget'
        bg_color = '#FFF8B5'

    window = webview.create_window(
        window_title,
        url=os.path.join(ui_dir, 'index.html') + f'?persona={persona}',
        js_api=api_obj,
        width=w,
        height=h,
        x=x if x >= 0 else None,
        y=y if y >= 0 else None,
        frameless=True,
        easy_drag=False,
        resizable=True,
        min_size=(280, 320),
        on_top=False,
        hidden=False,
        background_color=bg_color,
    )

    api_obj.set_window(window)

    # PID file (persona-specific so both can run simultaneously)
    pid_file = os.path.join(BASE_DIR, f'widget-{persona}.pid')
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    # System tray
    tray_icon = None
    tray_ref = {'icon': None}

    def show_window(icon=None, item=None):
        window.show()

    def quit_app(icon=None, item=None):
        if tray_icon:
            tray_icon.stop()
        window.destroy()

    def setup_tray():
        nonlocal tray_icon
        menu = pystray.Menu(
            pystray.MenuItem('Show Widget', show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', quit_app),
        )
        tray_icon = pystray.Icon(
            f'TodoWidget-{persona}',
            create_tray_icon(persona),
            window_title,
            menu,
        )
        tray_ref['icon'] = tray_icon
        tray_icon.run()

    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()

    # Reminder notifications (todo mode only, not honey pot)
    reminder_thread = threading.Thread(
        target=reminder_loop, args=(api_obj, tray_ref), daemon=True
    )
    reminder_thread.start()

    # Global hotkey: Alt+T to show/focus the widget
    def hotkey_listener():
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
                window.show()
                # Bring to front
                if api_obj._hwnd:
                    user32.SetForegroundWindow(api_obj._hwnd)

    hotkey_thread = threading.Thread(target=hotkey_listener, daemon=True)
    hotkey_thread.start()

    def on_loaded():
        # Find and cache the window handle by PID (reliable)
        time.sleep(0.5)
        api_obj._hwnd = find_hwnd_by_pid(os.getpid())
        hide_from_taskbar(api_obj._hwnd)
        apply_dwm_tweaks(api_obj._hwnd)

        # Apply saved settings
        try:
            t = read_tracker()
            opacity = t.get('windowOpacity', 100)
            if opacity < 100:
                api_obj.set_window_opacity(opacity)
        except Exception:
            pass

        # File watcher (always runs - catches local edits)
        watcher = threading.Thread(
            target=file_watcher, args=(api_obj, window), daemon=True
        )
        watcher.start()

        # Firebase real-time sync (if configured)
        if api_obj._firebase:
            api_obj._initial_firebase_sync()
            api_obj._start_firebase_listeners()

    webview.start(on_loaded, debug=False)

    if tray_icon:
        tray_icon.stop()
    try:
        os.remove(pid_file)
    except OSError:
        pass


if __name__ == '__main__':
    main()
