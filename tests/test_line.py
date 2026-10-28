import floating_monitor as fm

GB = 1024 ** 3
CFG = dict(fm.DEFAULTS)
RAM_OK = (8 * GB, 32 * GB, 25.0)
RED = f'<span foreground="{fm.RED}">'


def blocks(line):
    return line.split(" │ ")


def test_calm_line_has_no_red():
    line = fm.build_line(CFG, 12.0, 50.0, RAM_OK, (20, 45, 1 * GB, 12 * GB))
    assert line == "CPU  12% 50° │ RAM 8.0/32.0G  25% │ GPU  20% 45° 1.0G"
    assert RED not in line


def test_without_gpu_the_block_is_gone():
    assert len(blocks(fm.build_line(CFG, 5.0, None, RAM_OK))) == 2


def test_cpu_turns_red_by_usage_or_by_temperature():
    assert blocks(fm.build_line(CFG, 80.0, 40.0, RAM_OK))[0].startswith(RED)
    assert blocks(fm.build_line(CFG, 10.0, 85.0, RAM_OK))[0].startswith(RED)
    assert not blocks(fm.build_line(CFG, 79.0, 84.0, RAM_OK))[0].startswith(RED)


def test_cpu_without_temperature_shows_only_the_usage():
    assert blocks(fm.build_line(CFG, 7.0, None, RAM_OK))[0] == "CPU   7%"


def test_ram_turns_red_at_the_usage_limit():
    assert blocks(fm.build_line(CFG, 1.0, None, (26 * GB, 32 * GB, 81.0)))[1].startswith(RED)


def test_gpu_turns_red_by_usage_temperature_or_vram():
    base = (10, 40, 1 * GB, 12 * GB)
    for gpu in ((90, 40, 1 * GB, 12 * GB), (10, 83, 1 * GB, 12 * GB), (10, 40, 11 * GB, 12 * GB)):
        assert blocks(fm.build_line(CFG, 1.0, None, RAM_OK, gpu))[2].startswith(RED), gpu
    assert not blocks(fm.build_line(CFG, 1.0, None, RAM_OK, base))[2].startswith(RED)


def test_gpu_with_unknown_values():
    # sysfs (AMD/Intel) gives only the usage; NVML may fail on every field
    assert blocks(fm.build_line(CFG, 1.0, None, RAM_OK, (33, None, None, None)))[2] == "GPU  33%"
    assert blocks(fm.build_line(CFG, 1.0, None, RAM_OK, (None, None, None, None)))[2] == "GPU --"


def test_limits_come_from_the_config():
    cfg = dict(CFG, usage_limit=50)
    assert blocks(fm.build_line(cfg, 55.0, None, RAM_OK))[0].startswith(RED)
