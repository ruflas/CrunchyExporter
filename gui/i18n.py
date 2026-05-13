"""
Minimal i18n loader.

Locale files live in  <project_root>/locales/<lang>.json
Keys missing from the active locale fall back to the English (en) locale,
and keys missing from en fall back to the raw key string.

To add a new language:
  1. Copy locales/en.json to locales/<lang>.json
  2. Translate the values (not the keys)
  3. Set  ui.language: "<lang>"  in config.yaml
"""

import json
from pathlib import Path

_LOCALES_DIR = Path(__file__).parent.parent / "locales"

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
_lang: str = "en"


def load(lang: str) -> None:
    """Load a locale.  Falls back to 'en' for any missing keys."""
    global _strings, _fallback, _lang

    def _read(name: str) -> dict:
        p = _LOCALES_DIR / f"{name}.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}

    _fallback = _read("en")
    _strings  = _read(lang) if lang != "en" else _fallback
    _lang     = lang


def t(key: str, **kwargs) -> str:
    """Return the translated string for *key*, formatting with kwargs."""
    text = _strings.get(key) or _fallback.get(key) or key
    return text.format(**kwargs) if kwargs else text


def current_lang() -> str:
    return _lang


def available_langs() -> list[str]:
    if not _LOCALES_DIR.exists():
        return ["en"]
    return sorted(p.stem for p in _LOCALES_DIR.glob("*.json"))
