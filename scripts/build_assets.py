#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools>=4.47"]
# ///
"""Build the profile art from one source: hero, section bands, footer, PNG exports.

Usage
    uv run scripts/build_assets.py                          # write the SVGs into assets/
    uv run --with resvg-py scripts/build_assets.py --png    # also write the PNG exports
    uv run scripts/build_assets.py --check                  # exit 1 if assets/ is stale

How it works
    - All type is converted to outlines. GitHub serves README images in a sandbox
      that blocks external fonts, so nothing here loads a font at view time.
    - The geometry was measured from the LinkedIn banner and is stored in that
      banner's pixel space (2208 x 552). Every target scales from those numbers,
      so GitHub and LinkedIn stay the same design.
    - Output is deterministic: same inputs, byte-identical SVG files.
    - Image files that Claude delivers carry a Content Credentials (C2PA) block.
      It is provenance metadata, not part of the drawing, so --check ignores it.
      Rerunning this script writes the same drawing without the block.

To change the page
    - Sections: edit SECTIONS, rerun, and reference the new files in README.md.
      Bands are numbered in list order. Delete the SVGs of a section you drop;
      --check names any that are left behind.
    - Colors: edit the palette block.
    - Motion: edit CSS. Every animation is switched off under prefers-reduced-motion.

Fonts (SIL Open Font License 1.1, license texts in scripts/fonts/)
    Big Shoulders Bold, National Park Regular, Geist Mono Regular.
"""

from __future__ import annotations

import argparse
import functools
import itertools
import math
import random
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(__file__).resolve().parent / "fonts"
OUT = ROOT / "assets"

Point = tuple[float, float]
Place = Callable[[float, float], Point]

# --------------------------------------------------------------------------- palette

BG_TOP = "#0B1629"
BG_BOTTOM = "#172845"
INK = "#F5F8FC"  # name, section titles
TAG = "#D6E2F4"  # tagline
RULE = "#506481"  # hairlines
MUTED = "#7E96BC"  # url, index numbers
STAR = "#A9BEE8"  # constellation, panel edge
SIGNAL = "#DCE8FF"  # the travelling light

NODE_PEAK = 0.27  # node opacity at the top of a twinkle
NODE_REST = 0.52  # resting share of the peak (0.27 * 0.52 matches the banner)
RING_PEAK = 0.40
EDGE_OPACITY = 0.10
ORBIT_OPACITY = 0.05

# --------------------------------------------------------------------------- geometry
# Everything below is in the pixel space of the LinkedIn banner: 2208 x 552.

REF_W, REF_H = 2208.0, 552.0

NAME = "JEREMY GRACEY"
TAGLINE = "AGENT SYSTEMS THAT HOLD UP UNDER AUDIT"
URL = "jeremygracey.ai"

NAME_SIZE, NAME_TRACK, NAME_BASELINE = 185.0, 0.104, 292.5
RULE_Y, RULE_OVERHANG, RULE_WIDTH = 361.0, 4.0, 2.0
TAG_SIZE, TAG_TRACK, TAG_BASELINE = 34.5, 0.36, 430.0
URL_SIZE, URL_TRACK, URL_BASELINE, URL_MARGIN = 19.75, 0.03, 526.0, 38.5

# id: (x, y, kind, radius). An "anchor" is an invisible end point behind the name.
NODES: dict[str, tuple[float, float, str, float]] = {
    "a0": (37, 244, "ring", 4.5),
    "a1": (101, 174, "dot", 7.5),
    "a2": (193, 208, "ring", 5),
    "a3": (208, 129, "dot", 8),
    "a4": (269, 130, "dot", 6.5),
    "a5": (277, 221, "ring", 8),
    "a6": (337, 203, "dot", 6.5),
    "a7": (347, 134, "dot", 6.5),
    "b0": (430, 252, "dot", 7),
    "b1": (500, 194, "anchor", 0),
    "c0": (468, 349, "dot", 6),
    "c1": (467.5, 374, "dot", 4.5),
    "c2": (461, 388.5, "ring", 7.5),
    "c3": (458, 416, "dot", 6),
    "c4": (501.5, 406, "dot", 6),
    "s0": (1653, 111, "ring", 8),
    "s1": (1648, 134, "dot", 4.5),
    "s2": (1703, 271, "ring", 7),
    "s3": (1783, 391, "ring", 6.5),
    "t0": (1878, 370, "dot", 6.5),
    "t1": (1888, 408, "ring", 8),
    "u0": (1834, 221, "dot", 5),
    "u1": (1945, 161, "dot", 5.5),
    "u2": (1952, 246, "dot", 6.5),
    "u3": (2000, 224, "dot", 8),
    "u4": (2077, 189, "dot", 8),
    "v0": (2011, 329, "ring", 4.5),
    "v1": (2015, 339, "ring", 4.5),
    "v2": (2066, 445, "dot", 6.5),
}

EDGES: list[tuple[str, str]] = [
    ("a0", "a1"), ("a0", "a2"), ("a1", "a2"), ("a2", "a3"), ("a3", "a4"),
    ("a4", "a7"), ("a7", "a6"), ("a6", "a5"), ("a5", "a2"),
    ("b0", "b1"),
    ("c0", "c1"), ("c1", "c2"), ("c2", "c3"), ("c2", "c4"), ("c3", "c4"),
    ("s0", "s1"), ("s1", "s2"), ("s2", "s3"), ("s3", "t0"), ("t0", "t1"), ("t1", "s3"),
    ("u0", "s2"), ("u0", "u1"), ("u0", "u2"), ("u1", "u2"), ("u1", "u3"),
    ("u1", "u4"), ("u2", "u3"), ("u3", "u4"), ("u2", "v0"), ("v1", "v2"),
]  # fmt: skip

# (cx, cy, r): the two large orbit circles behind the clusters.
ORBITS = [(251.6, 253.6, 342.3), (1953.6, 286.3, 395.8)]

# Routes the travelling signal follows on the hero, as node ids.
ROUTES = [
    ["a0", "a2", "a3", "a4", "a7", "a6", "a5", "a2"],
    ["s0", "s1", "s2", "s3", "t0", "t1"],
    ["u0", "u1", "u4", "u3", "u2", "v0"],
]


class Fragment(NamedTuple):
    """A piece of the constellation reused on a section band.

    The first id is the entry node: it sits on the band's rule. `route` is the
    path the signal takes once it leaves the rule.
    """

    ids: list[str]
    route: list[str]
    scale: float

    @property
    def reach(self) -> float:
        """Banner pixels from the centre of the entry node to the fragment's right edge."""
        return max(NODES[n][0] + NODES[n][3] for n in self.ids) - NODES[self.ids[0]][0]


# Bands take these in turn, first band first.
FRAGMENTS = [
    Fragment(["a2", "a3", "a4", "a5", "a6", "a7"], ["a2", "a3", "a4", "a7"], 0.50),
    Fragment(["s3", "t0", "t1"], ["s3", "t0", "t1"], 0.80),
    Fragment(["u0", "u1", "u2", "u3", "u4"], ["u0", "u1", "u4"], 0.56),
]

# (file slug, title as drawn, accessible name)
SECTIONS = [
    ("built-with-roboflow", "BUILT WITH ROBOFLOW", "Built with Roboflow"),
    ("what-i-build", "WHAT I BUILD", "What I build"),
    ("beyond-the-pins", "BEYOND THE PINS", "Beyond the pins"),
    ("now", "NOW", "Now"),
]

# --------------------------------------------------------------------------- motion
# The hero keeps moving (twinkle, signals, satellites). Bands and the footer draw
# themselves in once and then hold still, so a long page is not repainting forever.

CSS = f"""
.e{{animation:draw .9s ease-out both}}
.r{{animation:draw 1.1s ease-out .15s both}}
.n{{animation:pop .7s ease-out both}}
.tw{{animation:pop .7s ease-out both,tw 7s ease-in-out infinite}}
.p{{animation-timing-function:linear}}
@keyframes draw{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}
@keyframes pop{{from{{opacity:0}}to{{opacity:{NODE_REST}}}}}
@keyframes tw{{0%,100%{{opacity:{NODE_REST}}}50%{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.e,.r,.n,.tw{{animation:none}}.p,.sat{{display:none}}}}
""".strip().replace("\n", "")

# A dash the length of the path, then a gap longer than the path: the stroke is
# whole at offset 0 and gone at offset 1, in every renderer.
DRAWN = 'pathLength="1" stroke-dasharray="1 2"'


# The Content Credentials block Claude's file delivery adds to an SVG: a namespace
# on the root element and one metadata element holding the signed manifest.
CREDENTIALS = re.compile(r' xmlns:c2pa="[^"]*"|<metadata><c2pa:manifest>.*?</c2pa:manifest></metadata>', re.DOTALL)


def drawing(svg: str) -> str:
    """The SVG without any Content Credentials block, for comparing against a fresh build."""
    return CREDENTIALS.sub("", svg)


def num(value: float, places: int = 1) -> str:
    """Format a number: fixed precision, no trailing zeros, no negative zero."""
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


# --------------------------------------------------------------------------- type


class _PathPen(BasePen):
    """Collect a glyph outline as SVG path commands, scaled and flipped into place."""

    def __init__(self, glyph_set, scale: float, dx: float, dy: float, out: list[str]):
        super().__init__(glyph_set)
        self.scale, self.dx, self.dy, self.out = scale, dx, dy, out

    def _pt(self, pt: Point) -> str:
        return f"{num(self.dx + pt[0] * self.scale, 2)} {num(self.dy - pt[1] * self.scale, 2)}"

    def _moveTo(self, pt):
        self.out.append(f"M{self._pt(pt)}")

    def _lineTo(self, pt):
        self.out.append(f"L{self._pt(pt)}")

    def _qCurveToOne(self, pt1, pt2):
        self.out.append(f"Q{self._pt(pt1)} {self._pt(pt2)}")

    def _curveToOne(self, pt1, pt2, pt3):
        self.out.append(f"C{self._pt(pt1)} {self._pt(pt2)} {self._pt(pt3)}")

    def _closePath(self):
        self.out.append("Z")


class Face:
    """One font file, read once, used to turn strings into outlines."""

    def __init__(self, filename: str):
        font = TTFont(FONTS / filename)
        cmap = font.getBestCmap()
        if cmap is None:
            raise ValueError(f"{filename} has no Unicode character map")
        self.glyphs = font.getGlyphSet()
        self.cmap: dict[int, str] = cmap
        self.advances = font["hmtx"]
        # fontTools builds table attributes at load time, so the type checker cannot see them.
        self.upm: int = font["head"].unitsPerEm  # pyright: ignore[reportAttributeAccessIssue]
        cap: int = font["OS/2"].sCapHeight  # pyright: ignore[reportAttributeAccessIssue]
        self.cap_height: float = cap / self.upm
        self._ink_cache: dict[str, tuple[float, float] | None] = {}

    def _ink(self, ch: str) -> tuple[float, float] | None:
        """Left and right ink edges of a glyph in em, or None for a blank."""
        if ch not in self._ink_cache:
            pen = BoundsPen(self.glyphs)
            self.glyphs[self.cmap[ord(ch)]].draw(pen)
            bounds = pen.bounds
            self._ink_cache[ch] = None if bounds is None else (bounds[0] / self.upm, bounds[2] / self.upm)
        return self._ink_cache[ch]

    def _layout(self, text: str, size: float, tracking: float) -> tuple[list[float], float, float]:
        """Pen x for each character, plus the ink extent of the whole string."""
        xs: list[float] = []
        x, ink_left, ink_right = 0.0, math.inf, -math.inf
        for ch in text:
            xs.append(x)
            ink = self._ink(ch)
            if ink:
                ink_left = min(ink_left, x + ink[0] * size)
                ink_right = max(ink_right, x + ink[1] * size)
            x += (self.advances[self.cmap[ord(ch)]][0] / self.upm + tracking) * size
        return xs, ink_left, ink_right

    def outline(
        self, text: str, size: float, x: float, baseline: float, *, tracking: float = 0.0, align: str = "left"
    ) -> tuple[str, float, float]:
        """Path data for `text`, aligned by its ink, plus the ink's left and right x.

        `tracking` is extra space after each glyph, in em. No kerning is applied,
        which is how the banner was set.
        """
        xs, left, right = self._layout(text, size, tracking)
        origin = {"left": x - left, "center": x - (left + right) / 2, "right": x - right}[align]
        out: list[str] = []
        for ch, pen_x in zip(text, xs, strict=True):
            if self._ink(ch):
                pen = _PathPen(self.glyphs, size / self.upm, origin + pen_x, baseline, out)
                self.glyphs[self.cmap[ord(ch)]].draw(pen)
        return "".join(out), origin + left, origin + right


@functools.cache
def faces() -> tuple[Face, Face, Face]:
    """Display, text, and mono faces."""
    return Face("BigShoulders-Bold.ttf"), Face("NationalPark-Regular.ttf"), Face("GeistMono-Regular.ttf")


# --------------------------------------------------------------------------- canvas


@dataclass
class Canvas:
    """An SVG under construction.

    animate=False gives a plain still for PNG export. loop=True keeps the scene
    moving after the entrance; loop=False draws it in once and stops.
    """

    width: float
    height: float
    title: str
    desc: str = ""
    animate: bool = True
    loop: bool = False
    radius: float = 0.0
    strength: float = 1.0  # multiplies constellation opacity; small art needs a little more
    body: list[str] = field(default_factory=list)
    keyframes: list[str] = field(default_factory=list)
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def add(self, markup: str) -> None:
        self.body.append(markup)

    def svg(self) -> str:
        w, h = num(self.width), num(self.height)
        desc = f'<desc id="d">{self.desc}</desc>\n' if self.desc else ""
        style = f"<style>{CSS}{''.join(self.keyframes)}</style>\n" if self.animate else ""
        clip = group = edge = ""
        if self.radius:
            clip = f'<clipPath id="c"><rect width="{w}" height="{h}" rx="{num(self.radius)}"/></clipPath>'
            group = ' clip-path="url(#c)"'
            # A hairline edge keeps the panel readable on GitHub's dark theme,
            # where the page is nearly the same navy.
            edge = (
                f'<rect x="1" y="1" width="{num(self.width - 2)}" height="{num(self.height - 2)}" '
                f'rx="{num(self.radius - 1)}" fill="none" stroke="{STAR}" stroke-opacity=".14" stroke-width="2"/>\n'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-labelledby="{"t d" if self.desc else "t"}">\n'
            f'<title id="t">{self.title}</title>\n{desc}'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>'
            f"</linearGradient>{clip}</defs>\n{style}"
            f'<g{group}>\n<rect width="{w}" height="{h}" fill="url(#g)"/>\n'
            + "\n".join(self.body)
            + f"\n</g>\n{edge}</svg>\n"
        )

    # -- shapes ---------------------------------------------------------------

    def text(self, d: str, fill: str) -> None:
        self.add(f'<path d="{d}" fill="{fill}"/>')

    def hairline(self, x1: float, x2: float, y: float, stroke_width: float, *, from_center: bool = False) -> None:
        """A horizontal rule. When animated it draws itself in on load."""
        attrs = f'fill="none" stroke="{RULE}" stroke-width="{num(stroke_width, 2)}"'
        if not self.animate:
            self.add(f'<path d="M{num(x1)} {num(y)}H{num(x2)}" {attrs}/>')
        elif from_center:
            mid = (x1 + x2) / 2
            self.add(f'<path d="M{num(mid)} {num(y)}H{num(x1)}" {attrs} {DRAWN} class="r"/>')
            self.add(f'<path d="M{num(mid)} {num(y)}H{num(x2)}" {attrs} {DRAWN} class="r"/>')
        else:
            self.add(f'<path d="M{num(x1)} {num(y)}H{num(x2)}" {attrs} {DRAWN} class="r"/>')

    def orbit(self, cx: float, cy: float, r: float, stroke_width: float, period: float) -> None:
        """A faint circle. When the scene loops, one slow satellite rides it."""
        self.add(
            f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="none" stroke="{STAR}" '
            f'stroke-opacity="{ORBIT_OPACITY}" stroke-width="{num(stroke_width, 2)}"/>'
        )
        if self.animate and self.loop:
            start = self.rng.randrange(360)
            self.add(
                f'<circle class="sat" cx="{num(cx + r)}" cy="{num(cy)}" r="{num(stroke_width * 1.6, 2)}" '
                f'fill="{STAR}" fill-opacity=".45"><animateTransform attributeName="transform" type="rotate" '
                f'from="{start} {num(cx)} {num(cy)}" to="{start + 360} {num(cx)} {num(cy)}" '
                f'dur="{num(period)}s" repeatCount="indefinite"/></circle>'
            )

    def node(self, cx: float, cy: float, r: float, kind: str, stroke: float, when: float) -> str:
        """Markup for one node: a filled dot or an open ring."""
        if kind == "dot":
            shape = (
                f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" '
                f'fill="{STAR}" fill-opacity="{num(NODE_PEAK * self.strength, 2)}"/>'
            )
        else:
            shape = (
                f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="none" stroke="{STAR}" '
                f'stroke-opacity="{num(RING_PEAK * self.strength, 2)}" stroke-width="{num(stroke, 2)}"/>'
            )
        if not self.animate:
            return f'<g opacity="{NODE_REST}">{shape}</g>'
        if not self.loop:
            return f'<g class="n" opacity="{NODE_REST}" style="animation-delay:{num(when, 2)}s">{shape}</g>'
        twinkle_at = when + 0.7 + self.rng.random() * 6
        period = 5.5 + self.rng.random() * 4
        style = f"animation-delay:{num(when, 2)}s,{num(twinkle_at, 2)}s;animation-duration:.7s,{num(period)}s"
        return f'<g class="tw" opacity="{NODE_REST}" style="{style}">{shape}</g>'

    def constellation(self, ids: list[str], place: Place, scale: float, *, delay: float = 0.0) -> None:
        """Draw the named nodes and every edge between them.

        `place` maps a banner-space point onto this canvas. Edges stop at the rim
        of each node so the translucent shapes never stack. Edges and nodes appear
        in the order of `ids`, which reads as the cluster wiring itself up.
        """
        keep = set(ids)
        order = {node: i for i, node in enumerate(ids)}
        stroke = max(1.0, 1.6 * scale)
        edges: list[str] = []

        for a, b in EDGES:
            if a not in keep or b not in keep:
                continue
            (ax, ay, _, ar), (bx, by, _, br) = NODES[a], NODES[b]
            p, q = place(ax, ay), place(bx, by)
            length = math.dist(p, q)
            if length <= (ar + br) * scale:
                continue
            ux, uy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
            x1, y1 = p[0] + ux * ar * scale, p[1] + uy * ar * scale
            x2, y2 = q[0] - ux * br * scale, q[1] - uy * br * scale
            when = delay + 0.12 * min(order[a], order[b])
            motion = f' {DRAWN} class="e" style="animation-delay:{num(when, 2)}s"' if self.animate else ""
            edges.append(f'<path d="M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}"{motion}/>')

        self.add(
            f'<g fill="none" stroke="{STAR}" stroke-opacity="{num(EDGE_OPACITY * self.strength, 2)}" '
            f'stroke-width="{num(stroke, 2)}" stroke-linecap="round">{"".join(edges)}</g>'
        )
        nodes: list[str] = []
        for node in ids:
            x, y, kind, r = NODES[node]
            if kind != "anchor":
                nodes.append(self.node(*place(x, y), r * scale, kind, stroke, delay + 0.12 * order[node]))
        self.add("".join(nodes))

    def signal(self, points: list[Point], radius: float, *, period: float, delay: float) -> None:
        """A small light that runs along `points`.

        In a looping scene it travels for part of `period` and waits out the rest.
        Otherwise it makes one pass lasting `period` seconds.
        """
        if not self.animate:
            return
        travel = 0.42 if self.loop else 1.0  # share of the cycle spent moving
        lengths = [math.dist(p, q) for p, q in itertools.pairwise(points)]
        total = sum(lengths)

        def at(point: Point) -> str:
            return f"transform:translate({num(point[0])}px,{num(point[1])}px)"

        frames = [f"0%{{{at(points[0])};opacity:0}}", f"{num(travel * 8, 2)}%{{opacity:.85}}"]
        run = 0.0
        for length, point in zip(lengths[:-1], points[1:-1], strict=True):
            run += length
            frames.append(f"{num(100 * travel * run / total, 2)}%{{{at(point)}}}")
        frames.append(f"{num(travel * 92, 2)}%{{opacity:.85}}")
        frames.append(f"{num(travel * 100, 2)}%{{{at(points[-1])};opacity:0}}")
        if self.loop:
            frames.append(f"100%{{{at(points[-1])};opacity:0}}")

        name = f"s{len(self.keyframes)}"
        self.keyframes.append(f"@keyframes {name}{{{''.join(frames)}}}")
        count = "infinite" if self.loop else "1"
        self.add(
            f'<circle class="p" r="{num(radius, 2)}" fill="{SIGNAL}" opacity="0" style="animation-name:{name};'
            f'animation-duration:{num(period)}s;animation-delay:{num(delay)}s;animation-iteration-count:{count}"/>'
        )


# --------------------------------------------------------------------------- scenes


def corner(width: float) -> float:
    """Corner radius that lands near 6 px once the art is scaled into the README column."""
    return 14.0 if width < 1000 else 12.0


def wide(height: float, *, animate: bool, radius: float = 0.0) -> str:
    """The 4:1 banner. The GitHub hero and the LinkedIn cover share this layout."""
    s = height / REF_H
    c = Canvas(REF_W * s, height, NAME.title(), f"{TAGLINE.capitalize()}. {URL}", animate, True, radius)
    big, sans, mono = faces()

    def place(x: float, y: float) -> Point:
        return x * s, y * s

    for (cx, cy, r), period in zip(ORBITS, (140, 190), strict=True):
        c.orbit(cx * s, cy * s, r * s, 2.0 * s, period)
    c.constellation([n for n in NODES if n[0] in "abc"], place, s, delay=0.2)
    c.constellation([n for n in NODES if n[0] in "stuv"], place, s, delay=0.5)
    for i, route in enumerate(ROUTES):
        c.signal([place(*NODES[n][:2]) for n in route], 2.6 * s, period=13 + 3 * i, delay=3 + 4.5 * i)

    d, x1, x2 = big.outline(NAME, NAME_SIZE * s, c.width / 2, NAME_BASELINE * s, tracking=NAME_TRACK, align="center")
    c.text(d, INK)
    c.hairline(x1 - RULE_OVERHANG * s, x2 + RULE_OVERHANG * s, RULE_Y * s, RULE_WIDTH * s, from_center=True)
    d, _, _ = sans.outline(TAGLINE, TAG_SIZE * s, c.width / 2, TAG_BASELINE * s, tracking=TAG_TRACK, align="center")
    c.text(d, TAG)
    d, _, _ = mono.outline(
        URL, URL_SIZE * s, c.width - URL_MARGIN * s, URL_BASELINE * s, tracking=URL_TRACK, align="right"
    )
    c.text(d, MUTED)
    return c.svg()


def compact(width: float, *, animate: bool, radius: float = 0.0) -> str:
    """The 2:1 layout for narrow screens and the repository social preview."""
    k = width / 800.0  # designed at 800 x 400
    s = k * 400 / REF_H * 0.94
    c = Canvas(width, width / 2, NAME.title(), f"{TAGLINE.capitalize()}. {URL}", animate, True, radius)
    big, sans, mono = faces()

    # Each cluster is moved as a block: the quad to the top left, the fan to the
    # top right, the small chain to the bottom left.
    def top_left(x: float, y: float) -> Point:
        return (x - 9) * s, (y - 89) * s

    def top_right(x: float, y: float) -> Point:
        return (x - 1021) * s, (y - 98) * s

    def bottom_left(x: float, y: float) -> Point:
        return (x - 420) * s, (y + 132) * s

    c.orbit(210 * k, 150 * k, 250 * k, 1.5 * k, 140)
    c.orbit(640 * k, 250 * k, 290 * k, 1.5 * k, 190)
    c.constellation([n for n in NODES if n[0] == "a"], top_left, s, delay=0.2)
    c.constellation(["u0", "u1", "u2", "u3", "u4"], top_right, s, delay=0.5)
    c.constellation(["c0", "c1", "c2", "c3", "c4"], bottom_left, s, delay=0.8)
    c.signal([top_left(*NODES[n][:2]) for n in ROUTES[0]], 2.4 * k, period=13, delay=3)
    c.signal([top_right(*NODES[n][:2]) for n in ("u0", "u1", "u4", "u3", "u2")], 2.4 * k, period=16, delay=7.5)

    d, x1, x2 = big.outline(NAME, 101 * k, width / 2, 196 * k, tracking=NAME_TRACK, align="center")
    c.text(d, INK)
    c.hairline(x1 - 2 * k, x2 + 2 * k, 232 * k, 1.5 * k, from_center=True)
    for line, baseline in (("AGENT SYSTEMS THAT", 277), ("HOLD UP UNDER AUDIT", 316)):
        d, _, _ = sans.outline(line, 27 * k, width / 2, baseline * k, tracking=0.34, align="center")
        c.text(d, TAG)
    d, _, _ = mono.outline(URL, 21 * k, width - 34 * k, 372 * k, tracking=URL_TRACK, align="right")
    c.text(d, MUTED)
    return c.svg()


def band(index: int, title: str, label: str, width: float, *, animate: bool = True) -> str:
    """A section header: index number, title, and a rule that runs into the constellation."""
    narrow = width < 1000
    height = 112.0
    mid = height / 2
    c = Canvas(width, height, label, animate=animate, radius=corner(width), strength=1.8)
    big, _, mono = faces()
    pad = 30.0 if narrow else 44.0
    size = 62.0 if narrow else 66.0

    d, _, x_index = mono.outline(f"{index:02d}", 21.0, pad, mid + mono.cap_height * 21.0 / 2)
    c.text(d, MUTED)
    d, _, x_title = big.outline(title, size, x_index + 22.0, mid + big.cap_height * size / 2, tracking=0.09)
    c.text(d, INK)

    # The fragment hangs off the right edge with its entry node on the rule. A title
    # too long for its own fragment takes the next one in the cycle that clears it.
    shrink = 0.72 if narrow else 1.0
    room = width - pad - x_title - 16.0  # what the title leaves, less a little air

    def fits(f: Fragment) -> bool:
        return (f.reach + NODES[f.ids[0]][3]) * f.scale * shrink <= room

    cycle = [FRAGMENTS[(index - 1 + i) % len(FRAGMENTS)] for i in range(len(FRAGMENTS))]
    fragment = next((f for f in cycle if fits(f)), None)
    if fragment is None:
        return c.svg()
    scale = fragment.scale * shrink
    entry_x, entry_y, _, entry_r = NODES[fragment.ids[0]]
    origin = width - pad - fragment.reach * scale

    def place(x: float, y: float) -> Point:
        return origin + (x - entry_x) * scale, mid + (y - entry_y) * scale

    c.constellation(fragment.ids, place, scale, delay=0.9)
    rule_start, rule_end = x_title + 30.0, origin - entry_r * scale
    if rule_end - rule_start > 24.0:
        c.hairline(rule_start, rule_end, mid, 1.4)
        route = [(rule_start, mid)] + [place(*NODES[n][:2]) for n in fragment.route]
        c.signal(route, 2.2, period=2.6, delay=1.3)
    return c.svg()


def footer(width: float, *, animate: bool = True) -> str:
    """The closing rule: the site address between two hairlines."""
    height = 84.0
    mid = height / 2
    c = Canvas(width, height, URL, animate=animate, radius=corner(width), strength=1.8)
    _, _, mono = faces()
    pad = 30.0 if width < 1000 else 44.0
    gap, r = 30.0, 5.0

    d, x1, x2 = mono.outline(URL, 21.0, width / 2, mid + 7.0, tracking=0.04, align="center")
    c.text(d, MUTED)
    c.hairline(x1 - gap - r, pad + r, mid, 1.4)  # both rules draw outward from the address
    c.hairline(x2 + gap + r, width - pad - r, mid, 1.4)
    stops = ((pad, "dot", r - 1), (x1 - gap, "ring", r), (x2 + gap, "ring", r), (width - pad, "dot", r - 1))
    c.add("".join(c.node(x, mid, radius, kind, 1.4, 0.3 * i) for i, (x, kind, radius) in enumerate(stops)))
    c.signal([(x1 - gap, mid), (pad, mid)], 2.2, period=2.4, delay=1.4)
    c.signal([(x2 + gap, mid), (width - pad, mid)], 2.2, period=2.4, delay=1.4)
    return c.svg()


# --------------------------------------------------------------------------- targets


def svg_targets() -> dict[str, str]:
    """Every SVG in assets/, by file name."""
    files = {
        "hero.svg": wide(400, animate=True, radius=corner(1600)),
        "hero-mobile.svg": compact(800, animate=True, radius=corner(800)),
        "footer.svg": footer(1600),
        "footer-mobile.svg": footer(800),
    }
    for i, (slug, title, label) in enumerate(SECTIONS, start=1):
        files[f"section-{slug}.svg"] = band(i, title, label, 1600)
        files[f"section-{slug}-mobile.svg"] = band(i, title, label, 800)
    return files


def png_targets() -> dict[str, tuple[str, int]]:
    """PNG exports: file name -> (still SVG, pixel width)."""
    return {
        "linkedin-banner.png": (wide(396, animate=False), 1584),
        "social-preview.png": (compact(1280, animate=False), 1280),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the profile art: SVGs for the README, PNGs for upload.")
    parser.add_argument("--png", action="store_true", help="also render the PNG exports (needs resvg-py)")
    parser.add_argument("--check", action="store_true", help="compare against assets/ instead of writing")
    args = parser.parse_args()

    files = svg_targets()
    if args.check:
        stale = [
            name
            for name, text in files.items()
            if not (OUT / name).exists() or drawing((OUT / name).read_text()) != text
        ]
        dropped = sorted(path.name for path in OUT.glob("section-*.svg") if path.name not in files)
        for name in stale:
            print(f"stale: assets/{name}")
        for name in dropped:
            print(f"no longer built: assets/{name}")
        if stale:
            print(f"{len(stale)} file(s) differ; rerun without --check")
        if dropped:
            print(f"{len(dropped)} file(s) belong to a removed section; delete them")
        if not (stale or dropped):
            print("assets are up to date")
        return 1 if stale or dropped else 0

    OUT.mkdir(exist_ok=True)
    for name, text in files.items():
        (OUT / name).write_text(text)
        print(f"wrote assets/{name} ({len(text.encode()) / 1024:.1f} kB)")

    if args.png:
        try:
            from resvg_py import svg_to_bytes
        except ImportError:
            print("PNG export needs resvg-py: uv run --with resvg-py scripts/build_assets.py --png", file=sys.stderr)
            return 1
        for name, (text, pixels) in png_targets().items():
            (OUT / name).write_bytes(bytes(svg_to_bytes(svg_string=text, width=pixels)))
            print(f"wrote assets/{name} ({pixels} px wide)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
