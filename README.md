# Todo Widget

personal tooling

A desktop "sticky note" todo widget (pywebview + HTML UI + system tray) with
streaks, quotes, reminders and optional Firebase sync. Runs on **Windows and Linux**.

## Windows

```bat
install.bat ritesh      :: or: install.bat riya
```

Auto-starts on boot; manage with `todo-up` / `todo-down` / `todo-restart` in PowerShell.
Global hotkey **Alt+T** shows/focuses the widget. Uninstall: `uninstall.bat ritesh`.

## Linux

Tested on Ubuntu/GNOME (Wayland). The installer uses [uv](https://docs.astral.sh/uv/)
to create the virtualenv (auto-installing uv if missing), pulls the system GUI
packages, wires the CLI commands, and adds a login autostart entry.

```bash
./install.sh ritesh     # or: ./install.sh riya
```

It creates the environment with uv (system site-packages so it can see the
system PyGObject/WebKit, which aren't pip-installable):

```bash
uv venv --system-site-packages .venv
uv pip install -r requirements.txt
```

and installs the system packages it needs:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1 \
                 gir1.2-ayatanaappindicator3-0.1 libnotify-bin
```

Manage it from a new terminal: `todo-up` / `todo-down` / `todo-restart` / `todo-show`
(and `todo-riya-*`). Uninstall: `./uninstall.sh ritesh`.

- **Show/focus:** Linux has no in-app global hotkey. Use the tray "Show Widget"
  item, or bind a key to `todo-show` via **GNOME Settings → Keyboard → Custom
  Shortcuts** (it signals the running widget to raise itself).
- **Tray icon** is optional. It needs the `pystray` + `Pillow` pip packages
  (`pip install "pystray>=0.19" "Pillow>=9.0"` — kept out of `requirements.txt`
  because Pillow is ~6 MB) **and** `gir1.2-ayatanaappindicator3-0.1` plus the
  AppIndicator GNOME extension (shipped/enabled on Ubuntu). Without any of these
  the widget still runs; reminders fall back to `notify-send` and you show the
  window with `todo-show`.
- **Data** lives in `~/.local/share/TodoWidget/` (Windows: `%LOCALAPPDATA%\TodoWidget`).
- **Window positioning** under native Wayland can be limited (the compositor may
  ignore programmatic move); the widget runs under XWayland where this works.

## Notes

- `widget.pyw` is the cross-platform app; all OS-specific behaviour is isolated in
  `lib/platform_compat.py`.
- The legacy pure-PowerShell/WPF scripts (`widget.ps1`, `reminder.ps1`, `lib/*.ps1`)
  are Windows-only and superseded by the Python widget; `reminder.py` is the
  cross-platform login-popup replacement for `reminder.ps1`.
