from pathlib import Path
import yaml

CONFIG_DIR = Path.home() / ".study-room"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "name": "",
    "email": "",
    "default_attendees": 1,
    "rooms": [f"Price Center Study Room {i}" for i in range(1, 9)],
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return dict(DEFAULT_CONFIG)

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    merged = {**DEFAULT_CONFIG, **data}
    return merged


def save_config(config: dict, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
