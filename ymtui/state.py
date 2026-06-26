"""Persisted session state (~/.config/ymtui/state.json).

Stores the last opened source, the last played track and its position so the
app can restore where you left off on the next launch.

Shape::

    {
      "source": {"type": "liked"}
              |  {"type": "chart"}
              |  {"type": "playlist", "kind": 3, "user_id": "123", "title": "…"}
              |  {"type": "search", "query": "…"},
      "track_id": "12345:678",
      "queue_index": 3,
      "position": 42.5
    }
"""
from __future__ import annotations

import json

from ymtui.config import CONFIG_DIR

STATE_FILE = CONFIG_DIR / 'state.json'


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix('.json.tmp')
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        tmp.replace(STATE_FILE)
    except OSError:
        pass
