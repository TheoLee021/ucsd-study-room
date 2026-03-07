import tempfile
import os
from pathlib import Path

from study_room.config import load_config, save_config, DEFAULT_CONFIG


def test_default_config_has_required_fields():
    assert "name" in DEFAULT_CONFIG
    assert "email" in DEFAULT_CONFIG
    assert "default_attendees" in DEFAULT_CONFIG
    assert "rooms" in DEFAULT_CONFIG
    assert len(DEFAULT_CONFIG["rooms"]) == 8


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = {
        "name": "Theo",
        "email": "theo@ucsd.edu",
        "default_attendees": 1,
        "rooms": ["Price Center Study Room 1"],
    }
    save_config(config, config_path)
    loaded = load_config(config_path)
    assert loaded["name"] == "Theo"
    assert loaded["email"] == "theo@ucsd.edu"


def test_load_config_creates_default_if_missing(tmp_path):
    config_path = tmp_path / "nonexistent" / "config.yaml"
    loaded = load_config(config_path)
    assert loaded == DEFAULT_CONFIG
    assert config_path.exists()


def test_load_config_merges_missing_keys(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("name: Theo\n")
    loaded = load_config(config_path)
    assert loaded["name"] == "Theo"
    assert "rooms" in loaded
