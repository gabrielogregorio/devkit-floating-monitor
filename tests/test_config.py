import json

import floating_monitor as fm


def test_no_file_gives_the_defaults(config_paths):
    assert fm.load_config() == fm.DEFAULTS


def test_saved_values_are_merged_over_the_defaults(config_paths):
    new, _ = config_paths
    new.parent.mkdir(parents=True)
    new.write_text(json.dumps({"x": 10, "y": 20, "locked": True}))
    cfg = fm.load_config()
    assert (cfg["x"], cfg["y"], cfg["locked"]) == (10, 20, True)
    assert cfg["usage_limit"] == 80  # a key missing from the file comes from DEFAULTS


def test_unknown_keys_are_dropped(config_paths):
    new, _ = config_paths
    new.parent.mkdir(parents=True)
    new.write_text(json.dumps({"x": 1, "something_old": 5}))
    assert "something_old" not in fm.load_config()


def test_the_pre_rename_config_is_carried_over(config_paths):
    _, legacy = config_paths
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"x": 1500, "y": 8, "sempre_acima": False, "transparente": False,
                                  "travado": True, "visivel": True, "limite_uso": 70,
                                  "limite_temp_cpu": 90, "limite_temp_gpu": 80}))
    cfg = fm.load_config()
    assert cfg == {"x": 1500, "y": 8, "always_on_top": False, "transparent": False, "locked": True,
                   "visible": True, "usage_limit": 70, "cpu_temp_limit": 90, "gpu_temp_limit": 80}


def test_the_current_config_wins_over_the_legacy_one(config_paths):
    new, legacy = config_paths
    for path, x in ((new, 1), (legacy, 2)):
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"x": x}))
    assert fm.load_config()["x"] == 1


def test_a_corrupt_or_non_object_file_falls_back(config_paths):
    new, _ = config_paths
    new.parent.mkdir(parents=True)
    for content in ("{not json", "[1, 2]"):
        new.write_text(content)
        assert fm.load_config() == fm.DEFAULTS


def test_save_writes_atomically_and_reloads(config_paths):
    new, _ = config_paths
    cfg = dict(fm.DEFAULTS, x=42)
    fm.save_config(cfg)
    assert json.loads(new.read_text())["x"] == 42
    assert not (new.parent / "config.json.tmp").exists()
    assert fm.load_config()["x"] == 42


def test_save_never_raises(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setattr(fm, "CONFIG_DIR", str(blocker / "sub"))  # parent is a file: makedirs fails
    monkeypatch.setattr(fm, "CONFIG_PATH", str(blocker / "sub" / "config.json"))
    fm.save_config(dict(fm.DEFAULTS))
