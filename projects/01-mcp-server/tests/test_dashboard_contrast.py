"""Text on the dashboard must stay readable in both themes.

A browser check found six styles at 3.2–3.7:1 in the light theme, all traced to one
token. Colour regressions are invisible to every other test, so the palette is checked
here: each text token against every surface it can sit on, in both themes.

WCAG AA: 4.5:1 for normal text, 3:1 for large text. Everything sampled here is small.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[3] / "assets" / "dashboard.css"
MIN_RATIO = 4.5

# Text tokens that render at small sizes, and the surfaces they appear on.
TEXT_TOKENS = ["--ink", "--ink-2", "--ink-3", "--accent"]
SURFACES = ["--ground", "--surface", "--sunken"]


def parse_block(pattern: str) -> dict[str, str]:
    """Pull `--token: #hex;` pairs out of the first block matching `pattern`."""
    css = CSS.read_text(encoding="utf-8")
    start = css.index(pattern) + len(pattern)
    block = css[start : css.index("}", start)]
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    channel = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    light, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


THEMES = {
    "light": ":root {",
    "dark": ':root[data-theme="dark"] {',
}


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("token", TEXT_TOKENS)
def test_text_token_is_readable_on_every_surface(theme: str, token: str):
    palette = parse_block(THEMES[theme])
    failures = []
    for surface in SURFACES:
        ratio = contrast(palette[token], palette[surface])
        if ratio < MIN_RATIO:
            failures.append(f"{token} on {surface}: {ratio:.2f}:1")
    assert not failures, f"{theme} theme below WCAG AA ({MIN_RATIO}:1): " + ", ".join(failures)


def test_no_colour_exists_only_in_the_dark_theme():
    """The classic unreadable-page bug: a colour defined only inside a theme block never
    applies to viewers on the default "system" setting, which stamps no attribute at all.

    The reverse is fine and intentional — the code blocks keep one dark palette in both themes,
    so those tokens are declared once in :root and never overridden."""
    light, dark = parse_block(THEMES["light"]), parse_block(THEMES["dark"])
    assert set(dark) <= set(light), f"defined only in dark: {sorted(set(dark) - set(light))}"


def test_semantic_colours_are_distinct_from_the_accent():
    """Status must not read as branding: good/warning/danger each differ from the accent."""
    palette = parse_block(THEMES["light"])
    for token in ("--ok", "--warn", "--danger"):
        assert palette[token] != palette["--accent"]
