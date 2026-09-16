"""Scripts must run on a console we don't control.

Found the hard way: demo.py used box-drawing characters and crashed with
UnicodeEncodeError on a Windows console defaulting to cp1252, while working fine
in a UTF-8 shell. Anything a reviewer runs from a clean clone stays ASCII.
"""

from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_script_output_is_encodable_on_a_legacy_console(script):
    text = script.read_text(encoding="utf-8")
    try:
        text.encode("cp1252")
    except UnicodeEncodeError as exc:
        offending = text[exc.start : exc.end]
        line = text[: exc.start].count("\n") + 1
        pytest.fail(f"{script.name}:{line} uses {offending!r}, which a cp1252 console cannot print")


def test_there_are_scripts_to_check():
    assert SCRIPTS, "no scripts found; this guard would pass vacuously"
