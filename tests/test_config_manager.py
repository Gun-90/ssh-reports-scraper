import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


def fresh_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("urls", raising=False)

    from models.ConfigManager import ConfigManager

    ConfigManager._instance = None
    return ConfigManager()


def test_get_urls_allows_missing_config_source(monkeypatch, tmp_path):
    config = fresh_config(monkeypatch, tmp_path)

    assert config.get_urls("MissingFirm") == []


def test_get_urls_raises_when_loaded_urls_missing_key(monkeypatch, tmp_path):
    config = fresh_config(monkeypatch, tmp_path)
    monkeypatch.setenv("urls", json.dumps({"LS_0": ["https://example.test/list"]}))

    from models.ConfigManager import MissingConfigError

    with pytest.raises(MissingConfigError, match="Missing urls config"):
        config.get_urls("Samsung_5")


def test_get_urls_uses_default_for_optional_lookup(monkeypatch, tmp_path):
    config = fresh_config(monkeypatch, tmp_path)
    monkeypatch.setenv("urls", json.dumps({"LS_0": ["https://example.test/list"]}))

    assert config.get_urls("OptionalFirm", default=["fallback"]) == ["fallback"]
