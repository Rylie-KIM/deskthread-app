"""Draw the DeskThread app icon and build DeskThread.icns.

    uv run python -B -m scripts.make_icon [--preview FILE.png]

The icon is a ribbon of clear glass folded into a loose "D", on a clear glass tile. The tile
is really half transparent in the file, so whatever is behind the icon shows through:
transparency is the point. Everything is drawn here from code; no outside image is used.

Needs Pillow (a development package) and the Mac's own `iconutil`.
"""

import argparse
import itertools
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "DeskThread.app" / "Contents" / "Resources" / "DeskThread.icns"
FINAL = 1024
K = 4  # draw at four times the size, then shrink: smooth edges
S = FINAL * K

ROYAL = (10, 23, 196)
BLUE = (28, 84, 236)
AZURE = (47, 155, 255)
CYAN = (150, 220, 255)
WHITE = (255, 255, 255)

RGBA = tuple[int, int, int, int]
Point = tuple[float, float]


def layer() -> Image.Image:
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def blur(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius * K))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def ramp(stops: list[tuple[float, tuple[int, int, int]]], t: float) -> tuple[int, int, int]:
    """Colour at position t along a list of (position, colour) stops."""
    for (t0, c0), (t1, c1) in itertools.pairwise(stops):
        if t <= t1:
            return mix(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


def spline(points: list[Point], steps: int) -> list[Point]:
    """A smooth curve through the points (Catmull-Rom), evenly sampled per span."""
    padded = [points[0], *points, points[-1]]
    out: list[Point] = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for step in range(steps):
            t = step / steps
            t2, t3 = t * t, t * t * t
            out.append(
                tuple(  # type: ignore[arg-type]
                    0.5
                    * (
                        2 * p1[k]
                        + (-p0[k] + p2[k]) * t
                        + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3
                    )
                    for k in (0, 1)
                )
            )
    out.append(points[-1])
    return out


def tile() -> tuple[Image.Image, Image.Image]:
    """The clear glass tile and its shape. More solid at the top, see-through below."""
    box = (100 * K, 100 * K, 924 * K, 924 * K)
    radius = 186 * K
    shape = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shape).rounded_rectangle(box, radius=radius, fill=255)

    out = layer()
    shadow = layer()
    ImageDraw.Draw(shadow).rounded_rectangle(
        (box[0] + 30 * K, box[1] + 70 * K, box[2] - 30 * K, box[3] + 34 * K),
        radius=radius,
        fill=(36, 72, 180, 78),
    )
    out = Image.alpha_composite(out, blur(shadow, 22))

    fall = Image.linear_gradient("L").resize((S, S))  # 0 at the top, 255 at the bottom
    body = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    body.putalpha(ImageChops.multiply(shape, fall.point(lambda v: int(168 - v * 0.36))))
    out = Image.alpha_composite(out, body)
    tint = Image.new("RGBA", (S, S), (196, 224, 255, 0))
    tint.putalpha(ImageChops.multiply(shape, fall.point(lambda v: int(v * 0.5))))
    out = Image.alpha_composite(out, tint)

    # A soft band of light across the top, kept inside the tile.
    light = Image.new("L", (S, S), 0)
    ImageDraw.Draw(light).ellipse((-140 * K, -520 * K, 1060 * K, 470 * K), fill=120)
    light = ImageChops.multiply(blur(light.convert("RGBA"), 26).getchannel("R"), shape)
    glow = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    glow.putalpha(light)
    out = Image.alpha_composite(out, glow)

    rim = layer()
    draw = ImageDraw.Draw(rim)
    draw.rounded_rectangle(box, radius=radius, outline=(255, 255, 255, 245), width=5 * K)
    inner = (box[0] + 6 * K, box[1] + 6 * K, box[2] - 6 * K, box[3] - 6 * K)
    draw.rounded_rectangle(inner, radius=radius - 6 * K, outline=(120, 176, 250, 80), width=2 * K)
    return Image.alpha_composite(out, rim), shape


def ribbon(centre: list[Point], half_widths: list[float]) -> Image.Image:
    """A band of glass along the centre line.

    Across its width the glass is clearer in the middle and denser at the edges, with one
    streak of reflected light; along its length the colour runs from royal blue to pale cyan.
    """
    n = len(centre)
    normals: list[Point] = []
    for i in range(n):
        x1, y1 = centre[max(i - 1, 0)]
        x2, y2 = centre[min(i + 1, n - 1)]
        length = math.hypot(x2 - x1, y2 - y1) or 1.0
        normals.append((-(y2 - y1) / length, (x2 - x1) / length))

    strips = 26
    along = [(0.0, ROYAL), (0.3, BLUE), (0.62, AZURE), (1.0, CYAN)]
    out = layer()
    draw = ImageDraw.Draw(out)
    for i in range(n - 1):
        t = i / (n - 2)
        base = ramp(along, t)
        for j in range(strips):
            s0, s1 = -1 + 2 * j / strips, -1 + 2 * (j + 1) / strips
            s = (s0 + s1) / 2
            dense = abs(s) ** 2.4  # 0 in the middle, 1 at the edges
            streak = math.exp(-(((s + 0.42) / 0.16) ** 2))  # reflected light, off-centre
            colour = mix(mix(base, WHITE, 0.16 + 0.5 * streak), ROYAL, 0.2 * dense)
            alpha = round(118 + 112 * dense + 40 * streak - 46 * t)
            quad = []
            for index, side in ((i, s0), (i + 1, s0), (i + 1, s1), (i, s1)):
                (x, y), (nx, ny), w = centre[index], normals[index], half_widths[index]
                quad.append(((x + nx * w * side) * K, (y + ny * w * side) * K))
            draw.polygon(quad, fill=(*colour, max(40, min(255, alpha))))

    for side, edge_colour in ((-1.0, (255, 255, 255, 250)), (1.0, (214, 238, 255, 205))):
        edge = [
            ((x + nx * w * side) * K, (y + ny * w * side) * K)
            for (x, y), (nx, ny), w in zip(centre, normals, half_widths, strict=True)
        ]
        draw.line(edge, fill=edge_colour, width=round(3.2 * K), joint="curve")
    return out


def draw_icon() -> Image.Image:
    glass, shape = tile()

    # The path of the ribbon: down the stem, round the bottom, up the bowl and back across
    # the top of the stem, so the two ends overlap like a folded strip.
    path = spline(
        [
            (372, 262), (378, 360), (378, 480), (380, 600), (400, 700),
            (462, 744), (556, 734), (650, 680), (714, 588), (724, 478), (680, 376),
            (590, 306), (480, 276), (372, 284), (292, 330),
        ],
        steps=40,
    )  # fmt: skip
    n = len(path)
    widths = []
    for i in range(n):
        t = i / (n - 1)
        swell = 0.6 + 0.4 * math.sin(math.pi * t) ** 0.7
        widths.append(62 * swell)

    band = ribbon(path, widths)
    shade = Image.new("RGBA", (S, S), (16, 40, 150, 0))
    shade.putalpha(band.getchannel("A").point(lambda v: int(v * 0.42)))
    shade = ImageChops.offset(blur(shade, 15), 10 * K, 22 * K)
    shade.putalpha(ImageChops.multiply(shade.getchannel("A"), shape))

    icon = Image.alpha_composite(glass, shade)
    icon = Image.alpha_composite(icon, band)

    return icon.resize((FINAL, FINAL), Image.Resampling.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--preview", type=Path, help="also write a comparison sheet here")
    args = parser.parse_args()
    icon = draw_icon()

    if args.preview:
        sheet = Image.new("RGB", (1500, 620), (236, 241, 251))
        ImageDraw.Draw(sheet).rectangle((750, 0, 1500, 620), fill=(26, 29, 44))
        for column in (0, 750):
            big = icon.resize((460, 460), Image.Resampling.LANCZOS)
            sheet.paste(big, (column + 40, 50), big)
            for row, size in enumerate((128, 64, 32, 16)):
                small = icon.resize((size, size), Image.Resampling.LANCZOS)
                sheet.paste(small, (column + 560, 60 + row * 140), small)
        sheet.save(args.preview)

    work = REPO / "DeskThread.iconset"
    work.mkdir(exist_ok=True)
    for points in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"
            size = points * scale
            icon.resize((size, size), Image.Resampling.LANCZOS).save(work / name)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        ["/usr/bin/iconutil", "-c", "icns", str(work), "-o", str(TARGET)], check=False
    )
    shutil.rmtree(work)
    print("icon written" if done.returncode == 0 else "iconutil failed")
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
