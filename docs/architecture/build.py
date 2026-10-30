"""Build the architecture diagrams in this folder, and their SVG and PNG exports.

    uv run python docs/architecture/build.py            # write both .html sources
    python3 docs/architecture/build.py --export         # also .svg and .png (needs Playwright)

Data-platform-integration layout from the diagram-design skill, JB Analytica skin. The .html
files are generated: change the drawing here, rebuild, and commit all outputs together.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent

# JB Analytica skin
PAPER = "#F6F8FB"
INK = "#182333"
MUTED = "#4B586D"
SOFT = "#62748A"
ACCENT = "#C96E00"
ACCENT_TINT = "rgba(250,147,6,0.12)"
LINK = "#0C6EBA"
SANS = "'Poppins', system-ui, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, monospace"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,400;0,500;0,600;1,400"
    "&family=JetBrains+Mono:wght@400;500&display=swap"
)
ZONE = (260, 72, 696, 336)


class Svg:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(
        self,
        x,
        y,
        s,
        size=12,
        weight=400,
        fill=INK,
        family=SANS,
        anchor="middle",
        spacing=None,
        italic=False,
    ):
        extra = f' letter-spacing="{spacing}"' if spacing else ""
        style = ' font-style="italic"' if italic else ""
        self.add(
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
            f'font-family="{family}" text-anchor="{anchor}"{extra}{style}>{escape(s)}</text>'
        )

    def label(self, cx, line_y, s, side_x=None):
        """Masked arrow label 8px above a horizontal stroke, or beside a vertical one."""
        w = ((len(s) * 5 + 8) + 3) // 4 * 4
        x0, y0 = (cx - w // 2, line_y - 20) if side_x is None else (side_x, line_y)
        self.add(f'<rect x="{x0}" y="{y0}" width="{w}" height="12" rx="2" fill="{PAPER}"/>')
        self.text(x0 + w // 2, y0 + 9, s, size=8, fill=SOFT, family=MONO, spacing="0.06em")

    def path(self, d, style):
        styles = {
            "primary": f'stroke="{ACCENT}" stroke-width="1.4" marker-end="url(#arrow-accent)"',
            "secondary": f'stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"',
            "trigger": (
                f'stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)"'
            ),
            "git": (
                f'stroke="{ACCENT}" stroke-width="1.2" stroke-dasharray="5,4" '
                'marker-end="url(#arrow-accent)"'
            ),
            "link": (
                f'stroke="{LINK}" stroke-width="1" stroke-dasharray="4,3" '
                'marker-end="url(#arrow-link)"'
            ),
        }
        self.add(f'<path d="{d}" fill="none" {styles[style]}/>')

    def tag(self, x, y, s, stroke):
        w = (len(s) * 5 + 12 + 3) // 4 * 4
        self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="12" rx="2" fill="none" '
            f'stroke="{stroke}" stroke-opacity="0.45" stroke-width="0.8"/>'
        )
        self.text(
            x + w // 2, y + 9, s, size=7, weight=500, fill=stroke, family=MONO, spacing="0.08em"
        )

    def node(self, x, y, w, h, role, name, sub, kind="side"):
        fills = {
            "side": ("rgba(75,88,109,0.06)", SOFT, MUTED, INK),
            "step": ("#ffffff", INK, INK, INK),
            "focal": (ACCENT_TINT, ACCENT, ACCENT, INK),
            "bar": ("rgba(24,35,51,0.05)", "rgba(24,35,51,0.32)", MUTED, INK),
            "link": ("rgba(12,110,186,0.06)", "rgba(12,110,186,0.35)", LINK, LINK),
        }
        fill, stroke, tag_color, name_color = fills[kind]
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>')
        self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1"/>'
        )
        self.tag(x + 8, y + 8, role, tag_color)
        cx, cy = x + w // 2, y + h // 2
        self.text(cx, cy + 4, name, size=12, weight=600, fill=name_color)
        if sub:
            self.text(cx, cy + 20, sub, size=9, fill=SOFT, family=MONO)

    def zone(self, title, mask_w):
        zx, zy, zw, zh = ZONE
        self.add(
            f'<rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="8" '
            'fill="rgba(24,35,51,0.025)" stroke="rgba(24,35,51,0.32)" stroke-width="1" '
            'stroke-dasharray="4,4"/>'
        )
        self.add(f'<rect x="{zx + 16}" y="{zy - 6}" width="{mask_w}" height="12" fill="{PAPER}"/>')
        self.text(
            zx + 20,
            zy + 4,
            title,
            size=8,
            weight=500,
            fill=MUTED,
            family=MONO,
            anchor="start",
            spacing="0.14em",
        )

    def source_links(self, labels):
        """Four sources (left column) into dlt's left edge, fanned at 184 / 212 / 228 / 240."""
        self.path("M200 124 H248 Q256 124 256 132 V176 Q256 184 264 184 H276", "secondary")
        self.path("M200 212 H276", "secondary")
        self.path("M200 300 H244 Q252 300 252 292 V236 Q252 228 260 228 H276", "secondary")
        self.path("M200 388 H256 Q264 388 264 380 V248 Q264 240 272 240 H276", "secondary")
        self._source_labels = labels

    def platform_links(self):
        self.path("M460 212 H516", "primary")
        self.path("M700 212 H756", "primary")
        self.path("M368 140 V176", "trigger")
        self.path("M848 140 V176", "trigger")

    def common_labels(self):
        spots = [(224, 124), (238, 212), (222, 300), (228, 388)]
        for i, s in enumerate(self._source_labels):
            self.label(*spots[i], s)
        self.label(488, 212, "WRITE")
        self.label(728, 212, "BUILD")
        self.label(None, 428, "GIT", side_x=616)

    def legend(self, items, focal_text):
        ly = 556
        self.add(
            f'<line x1="40" y1="{ly - 8}" x2="1160" y2="{ly - 8}" '
            'stroke="rgba(24,35,51,0.10)" stroke-width="0.8"/>'
        )
        self.text(
            40,
            ly + 12,
            "LEGEND",
            size=8,
            weight=500,
            fill=MUTED,
            family=MONO,
            anchor="start",
            spacing="0.14em",
        )
        x = 136
        for style, s in items:
            self.path(f"M{x} {ly + 8} H{x + 32}", style)
            self.text(x + 44, ly + 12, s, size=9, fill=MUTED, family=MONO, anchor="start")
            x += 44 + (len(s) * 6 + 3) // 4 * 4 + 48
        self.add(
            f'<rect x="{x}" y="{ly + 2}" width="20" height="12" rx="3" '
            f'fill="{ACCENT_TINT}" stroke="{ACCENT}" stroke-width="1"/>'
        )
        self.text(x + 32, ly + 12, focal_text, size=9, fill=MUTED, family=MONO, anchor="start")


def current_stack(d: Svg) -> None:
    """The stack as it runs in this repo."""
    d.source_links(["DUCKDB", "HTTPS", "HTTPS", "HTTPS"])
    d.platform_links()
    d.path("M940 212 H1000", "primary")
    d.path("M940 232 H964 Q972 232 972 240 V292 Q972 300 980 300 H1000", "primary")
    d.path("M608 460 V408", "git")
    d.zone("DATA PLATFORM · MOTHERDUCK EU", 244)
    d.common_labels()
    d.label(970, 212, "LIVE SQL")
    d.label(None, 264, "MF QUERY", side_x=916)
    for k, (role, name, sub) in enumerate(
        [
            ("DB", "Webshop", "model2data · synthetic"),
            ("API", "Open-Meteo", "daily weather"),
            ("API", "Frankfurter", "ECB exchange rates"),
            ("API", "Nager.Date", "public holidays"),
        ]
    ):
        d.node(40, 92 + k * 88, 160, 64, role, name, sub)
    d.node(276, 96, 664, 44, "DAG", "Orchestra", "", kind="bar")
    d.text(
        608,
        132,
        "daily 06:00 Europe/Brussels · 4 loads in parallel · state-aware dbt",
        size=9,
        fill=SOFT,
        family=MONO,
    )
    d.node(276, 176, 184, 72, "INGEST", "dlt", "4 pipelines · merge", kind="step")
    d.node(516, 176, 184, 72, "STORE", "MotherDuck", "raw_* → nga_marts", kind="focal")
    d.node(756, 176, 184, 72, "MODEL", "dbt + MetricFlow", "23 models · 29 metrics", kind="focal")
    d.text(940, 324, "One definition per metric:", size=12, fill=MUTED, anchor="end", italic=True)
    d.text(
        940,
        340,
        "the dashboard and Claude both compile from it.",
        size=12,
        fill=MUTED,
        anchor="end",
        italic=True,
    )
    d.node(1000, 180, 160, 64, "BI", "KPI dashboard", "Claude · live")
    d.node(1000, 268, 160, 64, "AI", "Claude answers", "nga metrics query")
    d.node(40, 460, 1120, 56, "GIT", "GitHub · JB-Analytica/next-gen-analytics", "", kind="bar")
    d.text(
        600,
        504,
        "pipelines · dbt + metrics · dashboard SQL and backup · CI — cloned by "
        "Orchestra on every run",
        size=9,
        fill=SOFT,
        family=MONO,
    )
    d.legend(
        [
            ("primary", "governed data flow"),
            ("secondary", "extract"),
            ("trigger", "scheduled by Orchestra"),
            ("git", "code and config"),
        ],
        "focal: store and metric layer",
    )


def front_ends(d: Svg) -> None:
    """The offer: one metric layer, the front end is the client's choice."""
    d.source_links(["DUCKDB", "SQL", "HTTPS", "FILES"])
    d.platform_links()
    d.path("M940 188 H960 Q968 188 968 180 V132 Q968 124 976 124 H1000", "primary")
    d.path("M940 212 H1000", "primary")
    d.path("M940 232 H964 Q972 232 972 240 V292 Q972 300 980 300 H1000", "primary")
    # dbt Charts (open-source `dct`) queries the marts through ref() and the dbt profile, not
    # MetricFlow (yet): it leaves the dbt node from the bottom, dashed, to set it apart.
    d.path("M848 248 V380 Q848 388 856 388 H1000", "link")
    d.path("M608 460 V408", "git")
    d.zone("DATA PLATFORM", 132)
    d.common_labels()
    d.label(None, 148, "MF SQL", side_x=920)
    d.label(970, 212, "MF QUERY")
    d.label(None, 264, "SYNC", side_x=936)
    d.label(924, 388, "REF() · MARTS")
    d.node(40, 92, 160, 64, "SYNTHETIC", "model2data", "before client access", kind="link")
    for k, (role, name, sub) in enumerate(
        [
            ("DB", "Databases", "Postgres · MySQL"),
            ("API", "SaaS APIs", "Shopify · Stripe"),
            ("FILE", "Files", "CSV · Sheets"),
        ],
        start=1,
    ):
        d.node(40, 92 + k * 88, 160, 64, role, name, sub)
    d.node(276, 96, 664, 44, "DAG", "Orchestra", "", kind="bar")
    d.text(608, 132, "scheduled loads and state-aware dbt", size=9, fill=SOFT, family=MONO)
    d.node(276, 176, 184, 72, "INGEST", "dlt", "any source · merge", kind="step")
    d.node(516, 176, 184, 72, "STORE", "Warehouse", "MotherDuck · BigQuery", kind="focal")
    d.node(756, 176, 184, 72, "METRICS", "dbt + MetricFlow", "one definition each", kind="focal")
    d.text(560, 316, "One metric layer, any front end:", size=12, fill=MUTED, italic=True)
    d.text(560, 332, "the client picks how they want to see it.", size=12, fill=MUTED, italic=True)
    for k, (role, name, sub) in enumerate(
        [
            ("BI", "Claude dashboard", "live · small teams"),
            ("AI", "Claude answers", "ask, still governed"),
            ("BI", "Lightdash", "self-serve BI"),
            ("BI", "dbt Charts", "open source · dct"),
        ]
    ):
        d.node(1000, 92 + k * 88, 160, 64, role, name, sub)
    d.node(40, 460, 1120, 56, "GIT", "GitHub", "", kind="bar")
    d.text(
        600,
        504,
        "sources · models · metrics · dashboards as code · CI — every change is a pull request",
        size=9,
        fill=SOFT,
        family=MONO,
    )
    d.legend(
        [
            ("primary", "governed metrics"),
            ("secondary", "extract"),
            ("trigger", "scheduled"),
            ("link", "marts, not MetricFlow yet"),
            ("git", "code"),
        ],
        "focal",
    )


PAGES: dict[str, tuple[Callable[[Svg], None], str, str, str, str]] = {
    "diagram": (
        current_stack,
        "Architecture · next-gen-analytics",
        "Noordkust data platform",
        "Four sources land in MotherDuck through dlt; dbt and MetricFlow turn them into governed "
        "metrics that a live Claude dashboard and Claude's answers both read. Orchestra runs it "
        "every morning.",
        "A synthetic webshop and three public APIs are loaded by dlt into MotherDuck, modelled by "
        "dbt with MetricFlow metrics, and served to a live Claude KPI dashboard and Claude "
        "answers; Orchestra schedules the loads and dbt daily and GitHub holds all code.",
    ),
    "front-ends": (
        front_ends,
        "Architecture · the small-company stack",
        "One metric layer, any front end",
        "Sources land in the warehouse through dlt, and every metric is defined once in dbt with "
        "MetricFlow. On top of that one layer the front end is a choice: a live Claude dashboard "
        "for small teams, Lightdash for self-serve BI, or dbt Charts boards rendered from the "
        "marts. Claude answers questions from the same definitions.",
        "Sources, including model2data synthetic data, are loaded by dlt into a warehouse and "
        "modelled once in dbt with MetricFlow; that single metric layer feeds a Claude dashboard, "
        "Claude answers and Lightdash, while dbt Charts boards read the dbt marts directly, with "
        "Orchestra scheduling and GitHub holding all code.",
    ),
}


def page(slug: str) -> str:
    draw, eyebrow, title, sub, desc = PAGES[slug]
    d = Svg()
    draw(d)
    body = "\n      ".join(d.parts)
    markers = "\n        ".join(
        f'<marker id="{i}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">'
        f'<polygon points="0 0, 8 3, 0 6" fill="{c}"/></marker>'
        for i, c in [("arrow", MUTED), ("arrow-accent", ACCENT), ("arrow-link", LINK)]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <link href="{escape(FONTS)}" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: {SANS}; background: {PAPER}; color: {INK}; min-height: 100vh;
      display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1200px; width: 100%; }}
    .eyebrow {{ font-family: {MONO}; font-size: 0.66rem; font-weight: 500;
      letter-spacing: 0.18em; text-transform: uppercase; color: {MUTED}; margin-bottom: 0.5rem; }}
    h1 {{ font-size: clamp(1.5rem, 2.4vw + 0.75rem, 1.75rem); font-weight: 400;
      letter-spacing: -0.01em; line-height: 1.15; margin-bottom: 0.4rem; }}
    .sub {{ color: {MUTED}; font-size: 0.9rem; margin-bottom: 1.5rem; max-width: 70ch; }}
    svg {{ width: 100%; min-width: 900px; display: block; }}
    .colophon {{ margin-top: 1.25rem; padding-top: 0.75rem;
      border-top: 1px solid rgba(24,35,51,0.12); font-family: {MONO}; font-size: 0.66rem;
      color: {MUTED}; letter-spacing: 0.04em; }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{escape(eyebrow)}</p>
    <h1>{escape(title)}</h1>
    <p class="sub">{escape(sub)}</p>
    <svg viewBox="0 0 1200 600" xmlns="http://www.w3.org/2000/svg" role="img" \
aria-labelledby="{slug}-title {slug}-desc">
      <title id="{slug}-title">{escape(title)}</title>
      <desc id="{slug}-desc">{escape(desc)}</desc>
      <defs>
        {markers}
      </defs>
      <rect width="100%" height="100%" fill="{PAPER}"/>
      {body}
    </svg>
    <p class="colophon">Generated by docs/architecture/build.py · JB Analytica skin</p>
  </div>
</body>
</html>
"""


def export_svg(html_path: Path) -> Path:
    svg = re.search(r"<svg\b.*?</svg>", html_path.read_text(), re.S)
    assert svg, f"no <svg> in {html_path}"
    out = svg.group(0).replace(
        "<defs>", f"<defs>\n        <style>@import url('{FONTS.replace('&', '&amp;')}');</style>", 1
    )
    out = re.sub(
        r'(fill|stroke)="rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d*\.?\d+)\s*\)"',
        lambda m: '{0}="#{1:02x}{2:02x}{3:02x}" {0}-opacity="{4}"'.format(
            m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
        ),
        out,
    )
    target = html_path.with_suffix(".svg")
    target.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + out + "\n")
    return target


def export_png(html_path: Path, scale: int = 2) -> Path:
    from playwright.sync_api import sync_playwright

    target = html_path.with_suffix(".png")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page(device_scale_factor=scale)
        tab.goto(html_path.as_uri())
        tab.wait_for_load_state("networkidle")
        tab.evaluate("document.fonts.ready")
        tab.locator("svg").first.screenshot(path=str(target), omit_background=True)
        browser.close()
    return target


if __name__ == "__main__":
    for slug in PAGES:
        html_path = HERE / f"{slug}.html"
        html_path.write_text(page(slug))
        print("wrote", html_path.name)
        if "--export" in sys.argv:
            print("wrote", export_svg(html_path).name)
            print("wrote", export_png(html_path).name)
