# Todo Widget

A cute desktop sticky-note todo widget with streak tracking, daily quotes, and a shared "Honey Pot" feature.

Built with Python + pywebview + HTML/CSS/JS. Data stored as markdown in OneDrive for phone sync.

## Quick Install

1. Make sure Python 3.10+ is installed
2. Double-click `install.bat`
3. Done! Desktop shortcuts are created automatically.

## Running

**Desktop shortcuts** (created by installer):
- `Todo Widget` - Ritesh's yellow sticky note
- `Riyas Todos` - Riya's pink sticky note

**PowerShell commands** (open a new terminal after install):
```
todo-up              # Launch Ritesh's widget
todo-down            # Close it
todo-restart         # Restart it

todo-riya-up         # Launch Riya's widget
todo-riya-down       # Close it
todo-riya-restart    # Restart it
```

**Manual launch:**
```
pythonw widget.pyw              # Ritesh's version
pythonw widget.pyw --for-riya   # Riya's version
```

## Features

- Sticky note look with handwriting font
- Rich text: bold, italic, underline, strikethrough, font sizing
- Streak tracking with milestone celebrations
- Daily motivational quotes (ZenQuotes API + fallback collection)
- Resizable frameless window (drag any edge/corner)
- System tray icon (minimize to tray, show/quit from tray)
- Hidden from taskbar
- File watcher for live reload (edit on phone, see changes on desktop)

## Honey Pot

Click the honey jar icon in the header to toggle "Honey Pot" mode - a shared love messages board.

- Both versions can read and write messages
- Messages sync via OneDrive
- Winnie the Pooh transition animation when toggling
- Place `honey-sound.mp3` in `ui/assets/` for a sound effect

## Data Files

Stored in `OneDrive/TodoWidget/`:

| File | Description |
|------|-------------|
| `todos.md` | Ritesh's todo list (GFM checkboxes) |
| `tracker.json` | Ritesh's streak, window position, settings |
| `riya-todos.md` | Riya's todo list |
| `riya-tracker.json` | Riya's settings |
| `honey-pot.md` | Shared love messages |

## Phone Editing

1. Install any markdown editor on your phone (Obsidian, iA Writer, or just the Files app)
2. Open the OneDrive `TodoWidget` folder
3. Edit `todos.md` / `riya-todos.md` / `honey-pot.md`
4. Changes sync via OneDrive and appear on the desktop widget within seconds

## Project Structure

```
D:\todo\
  widget.pyw          # Main Python entry point
  todo-cli.ps1        # PowerShell CLI commands
  install.bat         # One-click installer
  requirements.txt    # Python dependencies
  lib/
    markdown_io.py    # OneDrive detection + markdown parser
    streak.py         # Streak tracking
    quotes.py         # Daily quotes (API + fallback)
  ui/
    index.html        # Widget HTML
    style.css         # Styling (yellow + pink themes)
    app.js            # Frontend logic
    assets/           # Images + audio
```
