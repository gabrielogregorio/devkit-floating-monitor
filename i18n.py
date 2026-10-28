"""Desktop strings (menu, window and tray titles). English is the source text and the key;
PT_BR holds the Brazilian Portuguese line. The language comes from FM_LANG, then the usual
LANGUAGE / LC_ALL / LC_MESSAGES / LANG: pt* shows pt-BR, anything else English.
tests/test_i18n.py fails on a missing line, on different {placeholders} or on an unused line."""

import os

PT_BR = {
    "Floating Monitor": "Monitor flutuante",
    "Floating Monitor: on": "Monitor flutuante: ligado",
    "Floating Monitor: off": "Monitor flutuante: desligado",
    "On": "Ligado",
    "Always on top": "Sempre acima de tudo",
    "Transparent (white text)": "Transparente (texto branco)",
    "Lock position": "Travar posição",
    "Pause reading": "Pausar leitura",
    "Back to the screen corner": "Voltar pro canto da tela",
    "Open System Monitor": "Abrir Monitor do Sistema",
}


def detect_language(env=None) -> str:
    env = os.environ if env is None else env
    for name in ("FM_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name, "")
        if value:
            first = value.split(":")[0]
            return "pt-BR" if first.lower().startswith("pt") else "en"
    return "en"


LANG = detect_language()


def tr(text: str, lang: str | None = None, **values) -> str:
    lang = LANG if lang is None else lang
    line = PT_BR.get(text, text) if lang == "pt-BR" else text
    return line.format(**values) if values else line
