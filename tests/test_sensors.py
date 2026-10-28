import floating_monitor as fm


def write_stat(path, user, idle, iowait=0):
    path.write_text(f"cpu  {user} 0 0 {idle} {iowait} 0 0 0 0 0\ncpu0 1 2 3 4 5 6 7 8 9 10\n")


def test_cpu_usage_is_the_busy_share_of_the_delta(tmp_path, monkeypatch):
    stat = tmp_path / "stat"
    monkeypatch.setattr(fm, "STAT_PATH", str(stat))
    monkeypatch.setattr(fm, "HWMON_DIR", str(tmp_path / "none"))
    write_stat(stat, 100, 100)
    cpu = fm.Cpu()
    write_stat(stat, 175, 125)  # +75 busy, +25 idle
    assert cpu.usage() == 75.0
    write_stat(stat, 175, 125, iowait=100)  # iowait counts as idle
    assert cpu.usage() == 0.0


def test_cpu_usage_without_progress_is_zero(tmp_path, monkeypatch):
    stat = tmp_path / "stat"
    monkeypatch.setattr(fm, "STAT_PATH", str(stat))
    monkeypatch.setattr(fm, "HWMON_DIR", str(tmp_path / "none"))
    write_stat(stat, 10, 10)
    cpu = fm.Cpu()
    assert cpu.usage() == 0.0


def make_hwmon(root, index, name, sensors):
    d = root / f"hwmon{index}"
    d.mkdir(parents=True)
    (d / "name").write_text(name + "\n")
    for n, (label, millideg) in sensors.items():
        if label is not None:
            (d / f"temp{n}_label").write_text(label + "\n")
        (d / f"temp{n}_input").write_text(f"{millideg}\n")
    return d


def cpu_with_hwmon(tmp_path, monkeypatch):
    stat = tmp_path / "stat"
    write_stat(stat, 1, 1)
    monkeypatch.setattr(fm, "STAT_PATH", str(stat))
    monkeypatch.setattr(fm, "HWMON_DIR", str(tmp_path / "hwmon"))
    return fm.Cpu()


def test_temperature_prefers_the_cpu_driver_and_its_package_label(tmp_path, monkeypatch):
    root = tmp_path / "hwmon"
    make_hwmon(root, 0, "nvme", {1: ("Composite", 30000)})
    d = make_hwmon(root, 1, "k10temp", {1: ("Tccd1", 60000), 2: ("Tctl", 55500)})
    cpu = cpu_with_hwmon(tmp_path, monkeypatch)
    assert cpu.temp_path == str(d / "temp2_input")
    assert cpu.temp() == 55.5


def test_temperature_falls_back_to_temp1(tmp_path, monkeypatch):
    d = make_hwmon(tmp_path / "hwmon", 0, "coretemp", {1: (None, 47000)})
    cpu = cpu_with_hwmon(tmp_path, monkeypatch)
    assert cpu.temp_path == str(d / "temp1_input")
    assert cpu.temp() == 47.0


def test_no_known_sensor_means_no_temperature(tmp_path, monkeypatch):
    make_hwmon(tmp_path / "hwmon", 0, "acpitz", {1: (None, 40000)})
    (tmp_path / "hwmon" / "hwmon9").mkdir()  # no "name" file: skipped
    cpu = cpu_with_hwmon(tmp_path, monkeypatch)
    assert cpu.temp_path is None and cpu.temp() is None


def test_a_broken_sensor_reads_as_none(tmp_path, monkeypatch):
    d = make_hwmon(tmp_path / "hwmon", 0, "k10temp", {1: ("Tctl", 50000)})
    cpu = cpu_with_hwmon(tmp_path, monkeypatch)
    (d / "temp1_input").write_text("garbage")
    assert cpu.temp() is None


def test_read_ram_uses_mem_available(tmp_path, monkeypatch):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       16000 kB\nMemFree:         1000 kB\nMemAvailable:    4000 kB\n"
                       "Buffers:          100 kB\n")
    monkeypatch.setattr(fm, "MEMINFO_PATH", str(meminfo))
    used, total, pct = fm.read_ram()
    assert (used, total, pct) == (12000 * 1024, 16000 * 1024, 75.0)


def test_gpu_through_sysfs_when_there_is_no_nvml(tmp_path, monkeypatch):
    drm = tmp_path / "drm"
    (drm / "card0").mkdir(parents=True)
    busy = drm / "card1" / "device" / "gpu_busy_percent"
    busy.parent.mkdir(parents=True)
    busy.write_text("37\n")
    monkeypatch.setattr(fm, "DRM_DIR", str(drm))
    gpu = fm.Gpu(nvml_lib="libdoes-not-exist.so")
    assert gpu.present and gpu.nv is None
    assert gpu.read() == (37, None, None, None)
    busy.write_text("?")
    assert gpu.read() == (None, None, None, None)
    gpu.close()


def test_no_gpu_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(fm, "DRM_DIR", str(tmp_path / "missing"))
    gpu = fm.Gpu(nvml_lib="libdoes-not-exist.so")
    assert not gpu.present
    assert gpu.read() == (None, None, None, None)


def test_icons_are_written_on_and_off(tmp_path, monkeypatch):
    monkeypatch.setattr(fm, "ICONS_DIR", str(tmp_path / "icons"))
    fm.write_icons()
    on = (tmp_path / "icons" / f"{fm.ICON_NAME}-on.svg").read_text()
    off = (tmp_path / "icons" / f"{fm.ICON_NAME}-off.svg").read_text()
    assert on.startswith("<svg") and "#2ecc71" in on
    assert "#2ecc71" not in off and "#9a9a9a" in off
