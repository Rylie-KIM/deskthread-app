"""Draw the DeskThread app icon (a glass sphere on blue) and build DeskThread.icns.

    uv run python -B -m scripts.make_icon

Needs Pillow (a development package) and the Mac's own `iconutil`. The icon is drawn from
code; no outside image is used. The intermediate files are made in a folder that is removed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "DeskThread.app" / "Contents" / "Resources" / "DeskThread.icns"
SIZE = 1024


def vertical(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        draw.line(
            [(0, y), (SIZE, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    return img


def draw_icon() -> Image.Image:
    background = vertical((4, 8, 120), (14, 96, 240))
    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse((-200, 420, 760, 1320), fill=120)
    background = Image.composite(
        vertical((70, 170, 255), (30, 110, 250)),
        background,
        glow.filter(ImageFilter.GaussianBlur(90)),
    )
    # The sphere: light at the top left, deep blue at the bottom right.
    sphere = Image.new("RGB", (SIZE, SIZE))
    pixels = ImageDraw.Draw(sphere)
    cx, cy, radius = 512, 500, 300
    for r in range(radius, 0, -2):
        t = r / radius
        colour = (round(215 - 200 * t), round(238 - 180 * t), round(255 - 60 * t))
        ox, oy = (1 - t) * -95, (1 - t) * -105
        pixels.ellipse((cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r), fill=colour)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    shadow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shadow).ellipse((cx - 250, cy + 190, cx + 250, cy + 330), fill=150)
    dark = Image.new("RGB", (SIZE, SIZE), (2, 5, 80))
    background = Image.composite(dark, background, shadow.filter(ImageFilter.GaussianBlur(40)))
    background = Image.composite(sphere, background, mask.filter(ImageFilter.GaussianBlur(1.2)))
    # macOS icon shape: a rounded square with a margin.
    shape = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shape).rounded_rectangle((100, 100, 924, 924), radius=185, fill=255)
    icon = background.convert("RGBA")
    icon.putalpha(ImageChops.multiply(shape, Image.new("L", (SIZE, SIZE), 255)))
    return icon


def main() -> int:
    work = REPO / "DeskThread.iconset"
    work.mkdir(exist_ok=True)
    icon = draw_icon()
    for points in (16, 32, 128, 256, 512):
        icon.resize((points, points), Image.Resampling.LANCZOS).save(
            work / f"icon_{points}x{points}.png"
        )
        icon.resize((points * 2, points * 2), Image.Resampling.LANCZOS).save(
            work / f"icon_{points}x{points}@2x.png"
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        ["/usr/bin/iconutil", "-c", "icns", str(work), "-o", str(TARGET)], check=False
    )
    shutil.rmtree(work)
    print(
        f"icon written: {TARGET.relative_to(REPO)}" if done.returncode == 0 else "iconutil failed"
    )
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
