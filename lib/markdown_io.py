"""Markdown parser/writer for todo data with configurable storage path."""

import os
import re
import json
import threading

_file_lock = threading.Lock()

# --- Persona ---

_persona = 'ritesh'


def set_persona(persona):
    global _persona
    _persona = persona


def get_persona():
    return _persona


# --- Path configuration ---

def _get_config_path():
    """Path to widget-config.json next to this package."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'widget-config.json')


def get_configured_folder():
    """Read overridden folder path from widget-config.json, if it exists."""
    cfg = _get_config_path()
    if os.path.exists(cfg):
        try:
            with open(cfg, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
            folder = data.get('dataFolder')
            if folder and os.path.isdir(folder):
                return folder
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_configured_folder(folder_path):
    """Save a custom data folder path to widget-config.json."""
    cfg = _get_config_path()
    data = {}
    if os.path.exists(cfg):
        try:
            with open(cfg, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
        except (json.JSONDecodeError, IOError):
            pass
    data['dataFolder'] = folder_path
    with open(cfg, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2))


def get_widget_folder():
    # 1. Check config override (shared folder for Riya, or custom path)
    configured = get_configured_folder()
    if configured:
        return configured
    # 2. Default: local app data
    return os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'TodoWidget')


def get_todo_path():
    folder = get_widget_folder()
    if _persona == 'riya':
        return os.path.join(folder, 'riya-todos.md')
    return os.path.join(folder, 'todos.md')


def get_tracker_path():
    folder = get_widget_folder()
    if _persona == 'riya':
        return os.path.join(folder, 'riya-tracker.json')
    return os.path.join(folder, 'tracker.json')


def get_honey_pot_path():
    return os.path.join(get_widget_folder(), 'honey-pot.md')


def init_folder():
    folder = get_widget_folder()

    os.makedirs(folder, exist_ok=True)

    todo_path = get_todo_path()
    if not os.path.exists(todo_path):
        write_todo_file([], todo_path)

    tracker_path = get_tracker_path()
    if not os.path.exists(tracker_path):
        default = {
            'currentStreak': 0,
            'longestStreak': 0,
            'lastActiveDate': None,
            'lastReminder': None,
            'windowLeft': -1,
            'windowTop': -1,
            'windowWidth': 380,
            'windowHeight': 520,
            'fontSize': 16,
            'todayQuote': None,
            'todayQuoteDate': None,
        }
        write_json(tracker_path, default)

    honey_path = get_honey_pot_path()
    if not os.path.exists(honey_path):
        write_honey_pot_file([])


# --- File I/O ---

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    content = content.replace('\r\n', '\n')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)


def read_json(path):
    return json.loads(read_file(path))


def write_json(path, data):
    write_file(path, json.dumps(data, indent=2))


def read_tracker():
    path = get_tracker_path()
    if not os.path.exists(path):
        return {
            'currentStreak': 0, 'longestStreak': 0,
            'lastActiveDate': None, 'lastReminder': None,
            'windowLeft': -1, 'windowTop': -1,
            'windowWidth': 380, 'windowHeight': 520,
            'fontSize': 16,
            'todayQuote': None, 'todayQuoteDate': None,
        }
    return read_json(path)


def save_tracker(tracker):
    write_json(get_tracker_path(), tracker)


# --- Markdown Parsing ---

def read_todo_sections(path=None):
    if path is None:
        path = get_todo_path()
    if not os.path.exists(path):
        return []

    raw = read_file(path)
    lines = raw.split('\n')
    sections = []
    current = None

    for line in lines:
        trimmed = line.strip()

        m = re.match(r'^##\s+(\d{4}-\d{2}-\d{2})', trimmed)
        if m:
            if current:
                sections.append(current)
            current = {'date': m.group(1), 'items': []}
            continue

        if current is not None:
            m = re.match(r'^(\s*)-\s+\[([ xX])\]\s*(.*)$', line)
            if m:
                indent = len(m.group(1))
                depth = indent // 2
                done = m.group(2) != ' '
                text = m.group(3).strip()
                # Extract priority tag {p:high|medium|low}
                priority = 'none'
                pm = re.search(r'\s*\{p:(high|medium|low)\}\s*$', text)
                if pm:
                    priority = pm.group(1)
                    text = text[:pm.start()].strip()
                current['items'].append({'text': text, 'done': done, 'depth': depth, 'priority': priority})

    if current:
        sections.append(current)

    return sections


_PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2, 'none': 3}


def _sort_items_by_priority(items):
    """Sort items by priority, keeping parent-child groups together."""
    if not items:
        return items

    # Build groups: each group is a root (depth 0) item + its children
    groups = []
    current_group = None

    for item in items:
        depth = item.get('depth', 0)
        if depth == 0:
            current_group = [item]
            groups.append(current_group)
        elif current_group is not None:
            current_group.append(item)
        else:
            # Orphan child — treat as its own group
            current_group = [item]
            groups.append(current_group)

    # Stable sort groups by priority of root item
    groups.sort(key=lambda g: _PRIORITY_ORDER.get(g[0].get('priority', 'none'), 3))

    # Flatten back
    return [item for group in groups for item in group]


def write_todo_file(sections, path=None):
    if path is None:
        path = get_todo_path()

    title = "Riya's Todos" if _persona == 'riya' else 'My Todos'
    lines = [f'# {title}', '']
    for section in sections:
        sorted_items = _sort_items_by_priority(section['items'])
        lines.append(f"## {section['date']}")
        lines.append('')
        for item in sorted_items:
            check = 'x' if item['done'] else ' '
            indent = '  ' * item.get('depth', 0)
            priority = item.get('priority', 'none')
            ptag = f' {{p:{priority}}}' if priority and priority != 'none' else ''
            lines.append(f"{indent}- [{check}] {item['text']}{ptag}")
        lines.append('')

    content = '\n'.join(lines).rstrip() + '\n'
    write_file(path, content)


def get_today_str():
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')


def get_today_items():
    sections = read_todo_sections()
    today = get_today_str()
    for s in sections:
        if s['date'] == today:
            return s['items']
    return []


def get_previous_day_items():
    """Return items from the most recent section before today (handles gaps)."""
    sections = read_todo_sections()
    today = get_today_str()
    for s in sections:
        if s['date'] < today:
            return s['items']
    return []


def carry_over_yesterday():
    """Copy all items from the most recent previous day into today, reset to unchecked."""
    with _file_lock:
        sections = read_todo_sections()
        today = get_today_str()

        # Don't carry over if today already has items
        for s in sections:
            if s['date'] == today and s['items']:
                return

        # Find most recent previous day
        prev_items = None
        for s in sections:
            if s['date'] < today:
                prev_items = s['items']
                break

        if not prev_items:
            return

        # Copy items, reset done status
        new_items = [{'text': it['text'], 'done': False, 'depth': it.get('depth', 0), 'priority': it.get('priority', 'none')} for it in prev_items]

        # Insert or update today's section
        today_section = None
        for s in sections:
            if s['date'] == today:
                today_section = s
                break

        if today_section:
            today_section['items'] = new_items
        else:
            sections.insert(0, {'date': today, 'items': new_items})

        write_todo_file(sections)


def add_todo_item(text, depth=0, priority='none'):
    with _file_lock:
        sections = read_todo_sections()
        today = get_today_str()

        today_section = None
        for s in sections:
            if s['date'] == today:
                today_section = s
                break

        if not today_section:
            today_section = {'date': today, 'items': []}
            sections.insert(0, today_section)

        today_section['items'].append({'text': text, 'done': False, 'depth': depth, 'priority': priority})
        write_todo_file(sections)


def set_todo_done(date, index, done):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] != date or not (0 <= index < len(s['items'])):
                continue
            items = s['items']
            item = items[index]
            item_depth = item.get('depth', 0)
            item['done'] = done

            # Cascade to children: all deeper items immediately following
            for j in range(index + 1, len(items)):
                child_depth = items[j].get('depth', 0)
                if child_depth <= item_depth:
                    break
                items[j]['done'] = done

            # Bubble up: if checking done, check if all siblings under parent are done
            if done and item_depth > 0:
                parent_idx = None
                for j in range(index - 1, -1, -1):
                    if items[j].get('depth', 0) < item_depth:
                        parent_idx = j
                        break
                if parent_idx is not None:
                    parent_depth = items[parent_idx].get('depth', 0)
                    all_children_done = True
                    for j in range(parent_idx + 1, len(items)):
                        d = items[j].get('depth', 0)
                        if d <= parent_depth:
                            break
                        if d == item_depth and not items[j]['done']:
                            all_children_done = False
                            break
                    if all_children_done:
                        items[parent_idx]['done'] = True

            break
        write_todo_file(sections)


def remove_todo_item(date, index):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date and 0 <= index < len(s['items']):
                s['items'].pop(index)
                break
        write_todo_file(sections)


def update_todo_text(date, index, text):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date and 0 <= index < len(s['items']):
                s['items'][index]['text'] = text
                break
        write_todo_file(sections)


def clear_today_items(date):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date:
                s['items'] = []
                break
        write_todo_file(sections)


def set_today_items(date, items):
    """Replace all items for a given date (used by undo)."""
    with _file_lock:
        sections = read_todo_sections()
        found = False
        for s in sections:
            if s['date'] == date:
                s['items'] = items
                found = True
                break
        if not found:
            sections.insert(0, {'date': date, 'items': items})
        write_todo_file(sections)


def set_todo_priority(date, index, priority):
    valid = ('none', 'high', 'medium', 'low')
    if priority not in valid:
        priority = 'none'
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date and 0 <= index < len(s['items']):
                s['items'][index]['priority'] = priority
                break
        write_todo_file(sections)


def set_todo_depth(date, index, depth):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date and 0 <= index < len(s['items']):
                s['items'][index]['depth'] = max(0, min(3, depth))
                break
        write_todo_file(sections)


def reorder_todo_item(date, from_index, to_index):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] != date:
                continue
            items = s['items']
            if not (0 <= from_index < len(items) and 0 <= to_index < len(items)):
                break
            item = items.pop(from_index)
            items.insert(to_index, item)
            break
        write_todo_file(sections)


def reorder_todo_group(date, from_index, to_index, new_priority=None):
    """Move a task and all its children as a group to a new position.

    If new_priority is given, set the root item's priority (used when
    dragging across priority groups).
    """
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] != date:
                continue
            items = s['items']
            if not (0 <= from_index < len(items)):
                break

            # Collect the group: parent + all deeper children immediately following
            parent_depth = items[from_index].get('depth', 0)
            group_end = from_index + 1
            while group_end < len(items) and items[group_end].get('depth', 0) > parent_depth:
                group_end += 1
            group = items[from_index:group_end]
            del items[from_index:group_end]

            # Update priority of the root item if crossing groups
            if new_priority is not None:
                valid = ('none', 'high', 'medium', 'low')
                group[0]['priority'] = new_priority if new_priority in valid else 'none'

            # Adjust to_index after removal
            if to_index > from_index:
                to_index -= len(group)
            to_index = max(0, min(len(items), to_index))

            # Insert the group at the new position
            for i, item in enumerate(group):
                items.insert(to_index + i, item)
            break
        write_todo_file(sections)


def insert_todo_item(date, after_index, text, depth=0):
    with _file_lock:
        sections = read_todo_sections()
        for s in sections:
            if s['date'] == date:
                new_item = {'text': text, 'done': False, 'depth': max(0, min(3, depth)), 'priority': 'none'}
                s['items'].insert(after_index + 1, new_item)
                # Unmark ancestors: a done parent can't have an incomplete child
                items = s['items']
                new_idx = after_index + 1
                new_depth = new_item['depth']
                if new_depth > 0:
                    for j in range(new_idx - 1, -1, -1):
                        if items[j].get('depth', 0) < new_depth:
                            if items[j]['done']:
                                items[j]['done'] = False
                            new_depth = items[j].get('depth', 0)
                            if new_depth == 0:
                                break
                break
        write_todo_file(sections)


# --- Honey Pot ---

def read_honey_pot_messages():
    path = get_honey_pot_path()
    if not os.path.exists(path):
        return []
    raw = read_file(path)
    messages = []
    for line in raw.split('\n'):
        trimmed = line.strip()
        m = re.match(r'^-\s+(.+?)\s+~(\w+)\s*\((\d{4}-\d{2}-\d{2})\)$', trimmed)
        if m:
            messages.append({
                'text': m.group(1).strip(),
                'from': m.group(2).strip(),
                'date': m.group(3),
            })
    return messages


def add_honey_pot_message(text, from_persona):
    with _file_lock:
        messages = read_honey_pot_messages()
        today = get_today_str()
        messages.append({'text': text, 'from': from_persona, 'date': today})
        write_honey_pot_file(messages)


def update_honey_pot_message(index, text):
    with _file_lock:
        messages = read_honey_pot_messages()
        if 0 <= index < len(messages):
            messages[index]['text'] = text
        write_honey_pot_file(messages)


def remove_honey_pot_message(index):
    with _file_lock:
        messages = read_honey_pot_messages()
        if 0 <= index < len(messages):
            messages.pop(index)
        write_honey_pot_file(messages)


def clear_honey_pot_messages():
    with _file_lock:
        write_honey_pot_file([])


def write_honey_pot_file(messages, path=None):
    if path is None:
        path = get_honey_pot_path()
    lines = ['# Honey Pot', '']
    for msg in messages:
        lines.append(f"- {msg['text']} ~{msg['from']} ({msg['date']})")
    lines.append('')
    content = '\n'.join(lines).rstrip() + '\n'
    write_file(path, content)
