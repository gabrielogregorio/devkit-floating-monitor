"""install.sh for real, with HOME and the XDG dirs pointed into tmp_path."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def run(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_CONFIG_HOME=str(tmp_path / "config"))

    def runner(*args):
        return subprocess.run([str(ROOT / "install.sh"), *args], env=env, capture_output=True,
                              text=True, check=True)
    apps = tmp_path / "data" / "applications" / "devkit-floating-monitor.desktop"
    auto = tmp_path / "config" / "autostart" / "devkit-floating-monitor.desktop"
    return runner, apps, auto


def test_install_writes_the_shortcut_and_the_autostart_off(run):
    runner, apps, auto = run
    runner()
    shortcut = apps.read_text()
    assert f"Exec=/usr/bin/python3 {ROOT}/floating_monitor.py\n" in shortcut
    assert "Name[pt_BR]=Monitor flutuante" in shortcut
    autostart = auto.read_text()
    assert f"Exec=/usr/bin/python3 {ROOT}/floating_monitor.py --off\n" in autostart
    assert "X-GNOME-Autostart-Delay=3" in autostart


def test_no_autostart(run):
    runner, apps, auto = run
    runner("--no-autostart")
    assert apps.exists() and not auto.exists()


def test_remove(run):
    runner, apps, auto = run
    runner()
    out = runner("--remove").stdout
    assert not apps.exists() and not auto.exists()
    assert "removed" in out
