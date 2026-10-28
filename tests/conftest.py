"""Shared fixtures. The app module imports GTK 3 through PyGObject (python3-gi), but no test opens
a window: sensors read fake /proc and /sys trees in tmp_path and the config goes to tmp_path too."""
import pytest

import floating_monitor as fm


@pytest.fixture
def config_paths(tmp_path, monkeypatch):
    """Points the current and the pre-rename config files into tmp_path."""
    new = tmp_path / "config" / "config.json"
    legacy = tmp_path / "legacy" / "config.json"
    monkeypatch.setattr(fm, "CONFIG_DIR", str(new.parent))
    monkeypatch.setattr(fm, "CONFIG_PATH", str(new))
    monkeypatch.setattr(fm, "LEGACY_CONFIG_PATH", str(legacy))
    return new, legacy
