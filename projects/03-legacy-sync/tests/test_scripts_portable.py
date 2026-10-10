"""Anything a reviewer runs must print on a console we don't control (see project 01's post-mortem)."""

from pathlib import Path

SCRIPTS = sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.py"))


def test_every_script_is_encodable_on_a_legacy_console():
    assert SCRIPTS, "no scripts found; this guard would pass vacuously"
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        try:
            text.encode("cp1252")
        except UnicodeEncodeError as exc:
            line = text[: exc.start].count("\n") + 1
            raise AssertionError(f"{script.name}:{line} uses {text[exc.start:exc.end]!r}") from None
