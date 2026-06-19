"""Todo Widget - main entry point (pywebview + HTML UI + system tray)."""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview

# pystray + Pillow are OPTIONAL — they are only needed to draw the system-tray
# icon. Pillow is heavy (~6 MB) and pystray pulls it in, so neither is a core
# dependency. Without them the widget runs unchanged: reminders fall back to
# plat.notify() and the window is shown via the SIGUSR1/hotkey listener.
# pystray also selects its backend at import time; on Linux without an
# AppIndicator typelib that import raises — so the except covers both cases.
try:
    import pystray
except Exception:
    pystray = None

from lib import platform_compat as plat
from lib.markdown_io import (
    init_folder, get_todo_path, get_today_items, carry_over_yesterday, add_todo_item,
    set_todo_done, remove_todo_item, update_todo_text, set_todo_depth,
    set_todo_priority,
    reorder_todo_item, reorder_todo_group, insert_todo_item,
    clear_today_items, set_today_items, read_tracker, save_tracker,
    get_today_str, set_persona, get_persona, get_honey_pot_path,
    read_honey_pot_messages, add_honey_pot_message, update_honey_pot_message,
    remove_honey_pot_message, clear_honey_pot_messages,
    read_todo_sections, write_todo_file, write_honey_pot_file,
    _file_lock,
)
from lib.streak import update_streak, get_streak_display
from lib.quotes import get_daily_quote, get_time_greeting, get_poem_of_day

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


FIREBASE_URL = 'https://todo-app-acd7b-default-rtdb.firebaseio.com'

# Platform-specific window/OS behaviour lives in lib/platform_compat.py.


class Api:
    def __init__(self, persona='ritesh'):
        self._window = None
        self._hwnd = None
        self._last_mtime = 0
        self._last_honey_mtime = 0
        self._suppress_watch_until = 0
        self._suppress_fb_until = 0
        self._persona = persona
        self._honey_pot_mode = False
        self._tray_hidden = False
        self._restarting = False

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
            'platform': 'windows' if plat.IS_WINDOWS else ('mac' if plat.IS_MAC else 'linux'),
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

    def load_yesterday(self):
        carry_over_yesterday()
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
        return get_today_items()

    def confirm_and_clear_todos(self):
        # Native OS confirmation dialog (MessageBoxW on Windows, pywebview elsewhere)
        if not plat.confirm_dialog(
            self._window, "Clear All",
            "Clear all todos for today? This cannot be undone."
        ):
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

    def set_todo_priority(self, index, priority):
        set_todo_priority(get_today_str(), int(index), str(priority))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def reorder_todo(self, from_index, to_index):
        reorder_todo_item(get_today_str(), int(from_index), int(to_index))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def reorder_todo_group(self, from_index, to_index, new_priority=None):
        reorder_todo_group(get_today_str(), int(from_index), int(to_index),
                           new_priority=str(new_priority) if new_priority else None)
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def insert_todo_after(self, index, text, depth):
        insert_todo_item(get_today_str(), int(index), str(text).strip(), max(0, min(3, int(depth))))
        self._update_mtime()
        self._sync_todos()
        return get_today_items()

    def restore_todos(self, items):
        """Replace all today's items (used by undo)."""
        sanitized = []
        for item in (items or []):
            p = item.get('priority', 'none')
            if p not in ('none', 'high', 'medium', 'low'):
                p = 'none'
            sanitized.append({
                'text': item.get('text', ''),
                'done': bool(item.get('done', False)),
                'depth': max(0, min(3, int(item.get('depth', 0)))),
                'priority': p,
            })
        set_today_items(get_today_str(), sanitized)
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
        self._tray_hidden = True
        if self._window:
            self._window.hide()

    def get_window_rect(self):
        """Return the actual window rect {x, y, w, h} in physical pixels (or None)."""
        return plat.get_window_rect(self._hwnd)

    def resize_window(self, w, h):
        """Called from JS drag-resize handler."""
        if self._window:
            self._window.resize(int(w), int(h))

    def move_and_resize(self, x, y, w, h):
        """Atomic move+resize (SetWindowPos on Windows, pywebview elsewhere)."""
        plat.move_and_resize(self._hwnd, self._window, x, y, w, h)

    def start_window_move(self, x, y):
        """Begin a compositor-driven window move (Linux/GTK; no-op elsewhere)."""
        plat.start_window_move(self._window, x, y)

    def start_window_resize(self, edge, x, y):
        """Begin a compositor-driven resize from an edge (Linux/GTK; no-op elsewhere)."""
        plat.start_window_resize(self._window, str(edge), x, y)

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
        return read_honey_pot_messages()

    def delete_honey_pot_msg(self, index):
        remove_honey_pot_message(index)
        self._update_honey_mtime()
        self._sync_honeypot()
        return read_honey_pot_messages()

    def confirm_and_clear_honey_pot(self):
        if not plat.confirm_dialog(
            self._window, "Clear Honey Pot",
            "Clear all honey pot messages? This cannot be undone."
        ):
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
                self._suppress_fb_until = time.monotonic() + 2.0
                self._firebase.push_today_todos(today, items)
            except Exception:
                pass
        threading.Thread(target=_push, daemon=True).start()

    def _sync_honeypot(self):
        """Push honeypot messages to Firebase (background thread)."""
        if not self._firebase:
            return
        def _push():
            try:
                messages = read_honey_pot_messages()
                self._suppress_fb_until = time.monotonic() + 2.0
                self._firebase.push_honeypot(messages)
            except Exception:
                pass
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
            if time.monotonic() < self._suppress_fb_until:
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
                            'priority': item.get('priority', 'none'),
                        })

                # Update local file (under lock to prevent races)
                with _file_lock:
                    sections = read_todo_sections()
                    found = False
                    for s in sections:
                        if s['date'] == today:
                            s['items'] = items
                            found = True
                            break
                    if not found:
                        sections.insert(0, {'date': today, 'items': items})

                    self._suppress_watch_until = time.monotonic() + 3.0
                    write_todo_file(sections)
                    self._last_mtime = os.path.getmtime(get_todo_path())

                if self._window and not self._honey_pot_mode:
                    self._window.evaluate_js('refreshFromFile()')
            except Exception:
                pass

        # Listen for honeypot changes
        def on_honeypot_change(event_data):
            if time.monotonic() < self._suppress_fb_until:
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

                with _file_lock:
                    self._suppress_watch_until = time.monotonic() + 3.0
                    write_honey_pot_file(messages)
                    self._last_honey_mtime = os.path.getmtime(get_honey_pot_path())

                if self._window and self._honey_pot_mode:
                    self._window.evaluate_js('refreshHoneyPot()')
            except Exception:
                pass

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
                                'priority': item.get('priority', 'none'),
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
                        self._suppress_watch_until = time.monotonic() + 3.0
                        with _file_lock:
                            write_todo_file(sections)
                        self._last_mtime = os.path.getmtime(get_todo_path())

                        if self._window and not self._honey_pot_mode:
                            self._window.evaluate_js('refreshFromFile()')
            except Exception:
                pass

            # Also push current local state to Firebase (in case we have newer data)
            try:
                today = get_today_str()
                items = get_today_items()
                if items:
                    self._suppress_fb_until = time.monotonic() + 2.0
                    self._firebase.push_today_todos(today, items)
            except Exception:
                pass

            try:
                messages = read_honey_pot_messages()
                if messages:
                    self._suppress_fb_until = time.monotonic() + 2.0
                    self._firebase.push_honeypot(messages)
            except Exception:
                pass

        threading.Thread(target=_pull, daemon=True).start()

    # --- Settings ---

    SETTINGS_DEFAULTS = {
        'remindersEnabled': True,
        'reminderInterval': 10,
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
        """Set window opacity 50-100% (layered window on Windows, GTK elsewhere)."""
        plat.set_window_opacity(self._hwnd, self._window, pct)

    def restart_widget(self):
        """Relaunch widget as a detached process, then close this one."""
        args = [sys.executable, os.path.join(BASE_DIR, 'widget.pyw')]
        if self._persona == 'riya':
            args.append('--for-riya')
        # The relaunched child writes the same PID file; flag so our shutdown
        # cleanup doesn't delete the child's fresh PID file.
        self._restarting = True
        plat.spawn_detached(args, cwd=BASE_DIR)
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
                interval_min = tracker.get('reminderInterval', 10)

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
                            msg = random.choice(REMINDER_MESSAGES)
                            icon = tray_icon_ref.get('icon')
                            if icon:
                                icon.notify(msg, 'Todo Reminder')
                            else:
                                # No tray (e.g. Linux without AppIndicator) —
                                # fall back to a desktop notification.
                                plat.notify('Todo Reminder', msg)
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
        if time.monotonic() < api_obj._suppress_watch_until:
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
    """Build the tray-icon image. Requires Pillow; returns None if unavailable."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

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
        api_obj._tray_hidden = False
        window.show()

    def quit_app(icon=None, item=None):
        if tray_icon:
            tray_icon.stop()
        window.destroy()

    def setup_tray():
        nonlocal tray_icon
        try:
            icon_img = create_tray_icon(persona)
            if icon_img is None:
                # Pillow not installed — skip the tray entirely.
                tray_ref['icon'] = None
                return
            menu = pystray.Menu(
                pystray.MenuItem('Show Widget', show_window, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', quit_app),
            )
            tray_icon = pystray.Icon(
                f'TodoWidget-{persona}',
                icon_img,
                window_title,
                menu,
            )
            tray_ref['icon'] = tray_icon
            tray_icon.run()  # blocks; may raise on GNOME/Wayland without AppIndicator
        except Exception:
            # No system tray available — the app stays usable; reminders fall
            # back to plat.notify(). Signal the reminder loop via a None icon.
            tray_icon = None
            tray_ref['icon'] = None

    if pystray is not None:
        tray_thread = threading.Thread(target=setup_tray, daemon=True)
        tray_thread.start()

    # Reminder notifications (todo mode only, not honey pot)
    reminder_thread = threading.Thread(
        target=reminder_loop, args=(api_obj, tray_ref), daemon=True
    )
    reminder_thread.start()

    # Global "show/focus the widget" trigger:
    #   Windows  -> Alt+T global hotkey
    #   Linux/mac -> SIGUSR1 (sent by `todo-cli.sh show` / a GNOME shortcut)
    def on_show():
        api_obj._tray_hidden = False
        window.show()
        plat.raise_to_foreground(api_obj._hwnd)

    plat.start_show_listener(on_show)

    def on_loaded():
        # Find and cache the window handle by PID (Windows; None elsewhere)
        time.sleep(0.5)
        api_obj._hwnd = plat.find_hwnd_by_pid(os.getpid())
        plat.hide_from_taskbar(api_obj._hwnd)
        plat.apply_visual_tweaks(api_obj._hwnd)

        # Apply saved settings
        try:
            t = read_tracker()
            opacity = t.get('windowOpacity', 100)
            if opacity < 100:
                api_obj.set_window_opacity(opacity)
        except Exception:
            pass

        # Desktop persistence (restores widget after Win+D / Show Desktop).
        # Windows-only; a no-op on other platforms.
        plat.start_desktop_persist(api_obj, window)

        # File watcher (always runs - catches local edits)
        watcher = threading.Thread(
            target=file_watcher, args=(api_obj, window), daemon=True
        )
        watcher.start()

        # Firebase real-time sync (if configured)
        if api_obj._firebase:
            api_obj._initial_firebase_sync()
            api_obj._start_firebase_listeners()

    try:
        webview.start(on_loaded, debug=False)
    except Exception as e:
        sys.stderr.write(
            "Failed to start the webview GUI backend.\n"
            "On Linux install the GTK/WebKit backend, e.g.:\n"
            "  sudo apt install python3-gi gir1.2-webkit2-4.1\n"
            f"Underlying error: {e}\n"
        )
        raise

    if tray_icon:
        tray_icon.stop()
    # Skip PID cleanup if we're restarting — the relaunched child already
    # wrote a fresh PID file and we must not delete it.
    if not api_obj._restarting:
        try:
            os.remove(pid_file)
        except OSError:
            pass


if __name__ == '__main__':
    main()
