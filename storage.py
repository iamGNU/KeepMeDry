"""Encrypted storage for the subscriber list.

The file is committed to the repository's `data` branch by the workflow, so it is
encrypted with DATA_KEY: chat IDs and locations stay private even in a public repo.
"""

import json
from pathlib import Path

from cryptography.fernet import Fernet


def empty_data() -> dict:
    # offset: the next Telegram update ID to fetch.
    # subscribers: chat ID (as a string) -> {lat, lon, place, timezone, last_checked}
    return {"offset": 0, "subscribers": {}}


def load_data(path: Path, key: str) -> dict:
    if not path.exists():
        return empty_data()
    return json.loads(Fernet(key).decrypt(path.read_bytes()))


def save_data(path: Path, key: str, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(Fernet(key).encrypt(json.dumps(data, sort_keys=True).encode()))
