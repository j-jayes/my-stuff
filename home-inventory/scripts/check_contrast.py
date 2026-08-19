"""Assert the palette meets WCAG AA. Run after any change to tokens.css.

The blog's blue is light enough to fail on body text, so this is not a formality — it is the
check that keeps the palette honest.
"""

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).parent.parent / "frontend/src/styles/tokens.css"


def luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    lo, hi = sorted((la, lb))
    return (hi + 0.05) / (lo + 0.05)


def palette(css: str, dark: bool) -> dict[str, str]:
    # The dark palette is everything inside the prefers-color-scheme block.
    marker = "@media (prefers-color-scheme: dark)"
    light, _, night = css.partition(marker)
    source = light + night if dark else light
    found = {}
    for name, value in re.findall(r"(--[a-z-]+):\s*(#[0-9a-fA-F]{6})", source):
        found[name] = value.lower()
    return found


# (foreground, background, minimum, what it is)
PAIRS = [
    ("--text", "--bg", 4.5, "body text on the page"),
    ("--text", "--surface", 4.5, "body text on a card"),
    ("--text-strong", "--bg", 4.5, "emphasised text"),
    ("--muted", "--bg", 4.5, "muted text on the page"),
    ("--muted", "--surface", 4.5, "muted text on a card"),
    ("--accent", "--bg", 3.0, "headings (large text)"),
    ("--accent-strong", "--bg", 4.5, "links and small accent text"),
    ("--accent-strong", "--surface", 4.5, "links on a card"),
    ("--on-accent", "--accent-strong", 4.5, "button label on accent fill"),
    ("--danger", "--bg", 4.5, "error text"),
    ("--danger", "--surface", 4.5, "error text on a card"),
    ("--border-strong", "--bg", 1.5, "visible rule against the page"),
]

css = TOKENS.read_text()
failures = []
for dark in (False, True):
    colours = palette(css, dark)
    mode = "dark " if dark else "light"
    print(f"\n--- {mode} palette ---")
    for fg, bg, minimum, label in PAIRS:
        if fg not in colours or bg not in colours:
            failures.append(f"{mode}: {fg} or {bg} is not defined")
            continue
        r = ratio(colours[fg], colours[bg])
        ok = r >= minimum
        print(
            f"  {'ok  ' if ok else 'FAIL'} {r:5.2f}:1 (need {minimum})  "
            f"{colours[fg]} on {colours[bg]}  — {label}"
        )
        if not ok:
            failures.append(f"{mode}: {label} is {r:.2f}:1, needs {minimum}:1")

if failures:
    print("\nFAILED:")
    for f in failures:
        print(" ", f)
    sys.exit(1)
print("\nAll pairs pass.")
