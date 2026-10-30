"""Embed the Poppins brand face into a board that dbt Charts has already rendered.

dbt Charts vendors its own font families in a closed registry and offers no hook for an
`@font-face`. A board that asks for `Poppins` therefore renders `font-family: Poppins` with
nothing behind it and falls back to whatever the viewer has installed. This puts the real
bytes behind the name.

It rewrites generated output, which is why it is a separate step and not part of `dct render`:
the rendered file stays exactly what dbt Charts produced, plus one `<style>` block appended to
`<head>`, with the font files inlined as base64 so the page stays one self-contained file.

Known limit: dbt Charts measures text with the metrics of the family it believes it is
painting, then the browser paints Poppins, which is wider. Check a dense chart before trusting
it.

The woff2 files in `fonts/` are Poppins (SIL Open Font License 1.1).

    python charts/embed_brand_fonts.py charts/renders/noordkust_kpis.html
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

# Weights the board uses. Each one costs about 13 KB of woff2 in the output.
WEIGHTS = (400, 500, 600, 700)

UNICODE_RANGES = {
    "latin": (
        "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, "
        "U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, "
        "U+FEFF, U+FFFD"
    ),
    "latin-ext": (
        "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, "
        "U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, "
        "U+2113, U+2C60-2C7F, U+A720-A7FF"
    ),
}

FONT_DIR = Path(__file__).resolve().parent / "fonts"
MARKER = "<!-- brand-fonts -->"


def font_face_css() -> str:
    """One @font-face per weight per subset, with the woff2 inlined as a data URI."""
    rules = []
    for weight in WEIGHTS:
        for subset, unicode_range in UNICODE_RANGES.items():
            path = FONT_DIR / f"poppins-{weight}-{subset}.woff2"
            if not path.exists():
                raise SystemExit(f"missing font file: {path}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            rules.append(
                "@font-face{font-family:'Poppins';font-style:normal;"
                f"font-weight:{weight};font-display:swap;"
                f"src:url(data:font/woff2;base64,{encoded}) format('woff2');"
                f"unicode-range:{unicode_range}}}"
            )
    return "\n".join(rules)


def embed(html_path: Path) -> None:
    html = html_path.read_text(encoding="utf-8")

    if MARKER in html:
        print(f"{html_path}: already embedded, nothing to do")
        return
    if "</head>" not in html:
        raise SystemExit(f"{html_path}: no </head> to append to; is this a dct HTML render?")

    block = f"{MARKER}\n<style>\n{font_face_css()}\n</style>\n</head>"
    html_path.write_text(html.replace("</head>", block, 1), encoding="utf-8")

    size_mb = html_path.stat().st_size / 1_000_000
    print(f"{html_path}: embedded Poppins {WEIGHTS}, now {size_mb:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    embed(Path(sys.argv[1]))
