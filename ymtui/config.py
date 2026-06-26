"""Configuration loading from ~/.config/ymtui/config.ini.

Config file format (INI via configparser):

    [ymtui]
    token = y0_AgAEA...
"""
from __future__ import annotations

import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / '.config' / 'ymtui'
CONFIG_FILE = CONFIG_DIR / 'config.ini'
_SECTION = 'ymtui'


def load_config() -> dict[str, str]:
    cp = configparser.ConfigParser()
    cp.read(CONFIG_FILE)
    return dict(cp[_SECTION]) if cp.has_section(_SECTION) else {}


def save_config(config: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cp = configparser.ConfigParser()
    cp[_SECTION] = config
    with open(CONFIG_FILE, 'w') as f:
        cp.write(f)


def get_token() -> str | None:
    return load_config().get('token')
