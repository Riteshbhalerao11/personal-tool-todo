"""Firebase Realtime Database sync via REST API + SSE streaming."""

import json
import threading
import time
import requests


class FirebaseSync:
    """Simple Firebase REST client with SSE listener for real-time sync."""

    def __init__(self, db_url, persona):
        # Strip trailing slash
        self.db_url = db_url.rstrip('/')
        self.persona = persona
        self._listeners = []

    # --- REST operations ---

    def read(self, path):
        """GET /path.json → dict (or None on error)."""
        url = f"{self.db_url}/{path}.json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def write(self, path, data):
        """PUT /path.json → True on success."""
        url = f"{self.db_url}/{path}.json"
        try:
            resp = requests.put(url, json=data, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    # --- SSE listener ---

    def listen(self, path, callback):
        """Start a background daemon thread that listens for SSE events.

        callback(data) is called with the parsed JSON data on each 'put' or 'patch' event.
        Auto-retries on error after 5 seconds.
        """
        def _sse_loop():
            url = f"{self.db_url}/{path}.json"
            headers = {'Accept': 'text/event-stream'}
            while True:
                try:
                    with requests.get(url, headers=headers, stream=True, timeout=300) as resp:
                        if resp.status_code != 200:
                            time.sleep(5)
                            continue
                        event_type = None
                        data_lines = []
                        for raw_line in resp.iter_lines(chunk_size=1, decode_unicode=True):
                            if raw_line is None:
                                continue
                            line = raw_line
                            if line.startswith('event:'):
                                event_type = line[len('event:'):].strip()
                                data_lines = []
                            elif line.startswith('data:'):
                                data_lines.append(line[len('data:'):].strip())
                            elif line == '':
                                # End of event
                                if event_type in ('put', 'patch') and data_lines:
                                    raw_data = '\n'.join(data_lines)
                                    try:
                                        parsed = json.loads(raw_data)
                                        callback(parsed)
                                    except (json.JSONDecodeError, Exception):
                                        pass
                                event_type = None
                                data_lines = []
                except Exception:
                    pass
                # Retry after disconnect/error
                time.sleep(5)

        t = threading.Thread(target=_sse_loop, daemon=True)
        t.start()
        self._listeners.append(t)

    # --- High-level push helpers ---

    def push_todos(self, sections):
        """Push all todo sections for this persona, keyed by date.

        sections: list of {'date': 'YYYY-MM-DD', 'items': [{'text', 'done', 'depth'}, ...]}
        """
        for section in sections:
            date = section['date']
            items = []
            for item in section['items']:
                items.append({
                    'text': item.get('text', ''),
                    'done': item.get('done', False),
                    'depth': item.get('depth', 0),
                })
            self.write(f"todos/{self.persona}/{date}/items", items)

    def push_today_todos(self, today_str, items):
        """Push just today's todo items."""
        clean = []
        for item in items:
            clean.append({
                'text': item.get('text', ''),
                'done': item.get('done', False),
                'depth': item.get('depth', 0),
            })
        self.write(f"todos/{self.persona}/{today_str}/items", clean)

    def push_honeypot(self, messages):
        """Push honeypot messages list."""
        clean = []
        for msg in messages:
            clean.append({
                'text': msg.get('text', ''),
                'from': msg.get('from', ''),
                'date': msg.get('date', ''),
            })
        self.write("honeypot/messages", clean)

    def push_tracker(self, tracker):
        """Push tracker data (streak, settings)."""
        self.write(f"tracker/{self.persona}", tracker)
