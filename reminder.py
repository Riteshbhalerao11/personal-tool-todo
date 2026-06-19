"""Login reminder popup (cross-platform port of reminder.ps1).

Shows a small motivational popup once per day with a greeting, the current
streak and a quote (or a gentle roast if the streak is broken). Buttons let the
user open the widget or dismiss; it auto-closes after 30 seconds.

Launched at login from the XDG autostart entry created by install.sh. Reuses the
existing Python logic in lib/quotes.py, lib/streak.py and lib/markdown_io.py.
"""

import os
import sys
import html
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview

from lib import platform_compat as plat
from lib.markdown_io import init_folder, set_persona, read_tracker, save_tracker, get_today_str
from lib.streak import update_streak, get_streak_display
from lib.quotes import get_time_greeting, get_daily_quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mirrors Get-GentleRoast from lib/quotes.ps1 (used when the streak is broken).
GENTLE_ROASTS = [
    "Streak's gone, but legends are built on comebacks.",
    "A broken streak is just a plot twist. Start again.",
    "Yesterday's a memory. Today's a fresh page - write on it.",
    "The streak fell. Your resolve doesn't have to.",
    "Every comeback starts with a single checked box.",
]

# Catppuccin Mocha palette (same as reminder.ps1).
THEME = {
    'Base': '#1e1e2e', 'Mantle': '#181825', 'Surface0': '#313244',
    'Surface1': '#45475a', 'Text': '#cdd6f4', 'Subtext0': '#a6adc8',
    'Subtext1': '#bac2de', 'Green': '#a6e3a1', 'Peach': '#fab387',
    'Mauve': '#cba6f7', 'Crust': '#11111b',
}


def reminder_shown_today():
    return read_tracker().get('loginReminderDate') == get_today_str()


def mark_reminder_shown():
    tracker = read_tracker()
    tracker['loginReminderDate'] = get_today_str()
    save_tracker(tracker)


class ReminderApi:
    def __init__(self, persona):
        self._window = None
        self._persona = persona

    def set_window(self, window):
        self._window = window

    def open_widget(self):
        """Launch the main widget (detached) and close this popup."""
        args = [sys.executable, os.path.join(BASE_DIR, 'widget.pyw')]
        if self._persona == 'riya':
            args.append('--for-riya')
        try:
            plat.spawn_detached(args, cwd=BASE_DIR)
        except Exception:
            pass
        self.close()

    def close(self):
        if self._window:
            self._window.destroy()


def build_html(greeting, streak_display, quote_text, quote_author):
    t = THEME
    if quote_author:
        quote_html = (
            f'<span class="quote">&ldquo;{html.escape(quote_text)}&rdquo;</span>'
            f'<span class="author">&mdash; {html.escape(quote_author)}</span>'
        )
    else:
        quote_html = f'<span class="quote">{html.escape(quote_text)}</span>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden;
    font-family: 'Segoe UI', 'Ubuntu', system-ui, sans-serif; user-select: none; }}
  .card {{ margin: 8px; padding: 24px; border-radius: 16px;
    background: {t['Base']}; border: 1px solid {t['Surface1']};
    box-shadow: 0 8px 24px rgba(0,0,0,0.6); text-align: center; }}
  .greeting {{ font-size: 18px; font-weight: 700; color: {t['Mauve']}; margin-bottom: 8px; }}
  .streak {{ font-size: 14px; font-weight: 600; color: {t['Peach']}; margin-bottom: 14px; }}
  .quotebox {{ background: {t['Mantle']}; border-radius: 8px; padding: 12px 14px;
    margin-bottom: 18px; }}
  .quote {{ display: block; font-size: 12px; font-style: italic; color: {t['Subtext1']}; }}
  .author {{ display: block; font-size: 11px; color: {t['Subtext0']}; margin-top: 6px; }}
  .buttons {{ display: flex; gap: 12px; justify-content: center; }}
  button {{ border: none; border-radius: 8px; padding: 9px 16px; font-size: 13px;
    cursor: pointer; }}
  .open {{ background: {t['Green']}; color: {t['Crust']}; font-weight: 600; }}
  .dismiss {{ background: {t['Surface0']}; color: {t['Subtext0']}; }}
</style>
</head>
<body>
  <div class="card">
    <div class="greeting">{html.escape(greeting)}</div>
    <div class="streak">{html.escape(streak_display)}</div>
    <div class="quotebox">{quote_html}</div>
    <div class="buttons">
      <button class="open" onclick="pywebview.api.open_widget()">Open Todo Widget</button>
      <button class="dismiss" onclick="pywebview.api.close()">Not now</button>
    </div>
  </div>
</body>
</html>"""


def main():
    persona = 'riya' if '--for-riya' in sys.argv else 'ritesh'
    set_persona(persona)
    init_folder()

    # Show at most once per day (unless --force is passed, for testing).
    if '--force' not in sys.argv and reminder_shown_today():
        return
    mark_reminder_shown()

    streak_info = update_streak()
    streak_display = get_streak_display()
    greeting = get_time_greeting()

    if streak_info.get('broken'):
        import random
        quote_text = random.choice(GENTLE_ROASTS)
        quote_author = ''
    else:
        q = get_daily_quote()
        quote_text = q.get('text', '')
        quote_author = q.get('author', '')

    api = ReminderApi(persona)
    window = webview.create_window(
        'Daily Todo Reminder',
        html=build_html(greeting, streak_display, quote_text, quote_author),
        js_api=api,
        width=400,
        height=300,
        frameless=True,
        easy_drag=True,
        resizable=False,
        on_top=True,
        background_color=THEME['Base'],
    )
    api.set_window(window)

    def auto_dismiss():
        time.sleep(30)
        try:
            window.destroy()
        except Exception:
            pass

    threading.Thread(target=auto_dismiss, daemon=True).start()

    try:
        webview.start()
    except Exception as e:
        sys.stderr.write(f"Reminder popup failed to start GUI backend: {e}\n")


if __name__ == '__main__':
    main()
