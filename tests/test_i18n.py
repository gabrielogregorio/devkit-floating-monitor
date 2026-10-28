import re
from pathlib import Path

import i18n

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "floating_monitor.py"]
TR_CALL = re.compile(r'\btr\(\s*"((?:[^"\\]|\\.)*)"')
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def used_strings():
    found = set()
    for path in SOURCES:
        found.update(TR_CALL.findall(path.read_text(encoding="utf-8")))
    return found


def test_every_string_has_a_pt_br_line():
    missing = used_strings() - set(i18n.PT_BR)
    assert not missing, f"add these to PT_BR in i18n.py: {sorted(missing)}"


def test_no_unused_pt_br_line():
    unused = set(i18n.PT_BR) - used_strings()
    assert not unused, f"no longer used, remove from PT_BR: {sorted(unused)}"


def test_placeholders_match():
    for en, pt in i18n.PT_BR.items():
        assert set(PLACEHOLDER.findall(en)) == set(PLACEHOLDER.findall(pt)), en


def test_detect_language():
    assert i18n.detect_language({}) == "en"
    assert i18n.detect_language({"LANG": "pt_BR.UTF-8"}) == "pt-BR"
    assert i18n.detect_language({"LANG": "en_US.UTF-8"}) == "en"
    assert i18n.detect_language({"LANGUAGE": "pt_BR:en", "LANG": "en_US.UTF-8"}) == "pt-BR"
    assert i18n.detect_language({"FM_LANG": "en", "LANG": "pt_BR.UTF-8"}) == "en"


def test_tr():
    assert i18n.tr("On", lang="en") == "On"
    assert i18n.tr("On", lang="pt-BR") == "Ligado"
    assert i18n.tr("not in the catalog", lang="pt-BR") == "not in the catalog"
    assert i18n.tr("{n} x", lang="en", n=3) == "3 x"
