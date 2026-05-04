import os
import json

STATE_FILE = "state.json"


def load_state() -> dict:
    """Load persisted state from disk. Returns empty state if file doesn't exist."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"task_statuses": {}, "last_digest_date": None}


def save_state(state: dict) -> None:
    """Persist state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)