#!/usr/bin/env python3
# ruff: noqa: E501
"""Render the Avvalo icon set from deterministic vector-style drawing.

The master icon is generated from measured shapes, not an AI bitmap. Outputs
land in app/web/static:

- telegram-avatar-512.png  Telegram bot avatar upload (BotFather /setuserpic)
- telegram-bot-icon-512.png compatibility alias for the same Telegram avatar
- icon-512.png             web icon / PWA source
- icon-192.png             Android / PWA icon slot
- apple-touch-icon.png     180x180 iOS home-screen icon
- favicon.ico              16/32/48 legacy favicon, served at /favicon.ico
- icon.svg                 vector fallback matching the same blue/gold direction

Not part of the app runtime. Requires: pip install pillow
Run from the repo root: python tools/make_icons.py
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
BASE_SIZE = 512
SCALE = 4
WORK_SIZE = BASE_SIZE * SCALE

BLUE_TOP = (0, 138, 168)
BLUE_BOTTOM = (0, 68, 93)
BLUE_DEEP = (0, 72, 92)
BLUE_INK = (0, 58, 78)
GOLD = (217, 173, 58)
GOLD_DARK = (171, 126, 37)
WHITE = (255, 255, 250)

PNG_OUTPUTS = {
    "telegram-avatar-512.png": 512,
    "telegram-bot-icon-512.png": 512,
    "icon-512.png": 512,
    "icon-192.png": 192,
    "apple-touch-icon.png": 180,
}
ICO_SIZES = (48, 32, 16)


def u(value: float) -> int:
    """Scale a base 512-coordinate value to the high-resolution work canvas."""

    return round(value * SCALE)


def rgba(color: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color, alpha)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[index] * (1 - t) + b[index] * t) for index in range(3))


def pxy(points: Iterable[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(u(x), u(y)) for x, y in points]


def draw_round_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: float,
    fill: tuple[int, int, int, int],
) -> None:
    scaled_width = u(width)
    start_px = (u(start[0]), u(start[1]))
    end_px = (u(end[0]), u(end[1]))
    radius = scaled_width // 2
    draw.line([start_px, end_px], fill=fill, width=scaled_width)
    for x, y in (start_px, end_px):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)


def draw_diamond(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
    *,
    fill: tuple[int, int, int, int],
) -> None:
    cx, cy = center
    draw.polygon(
        pxy([(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)]),
        fill=fill,
    )


def draw_background() -> Image.Image:
    image = Image.new("RGBA", (WORK_SIZE, WORK_SIZE), rgba(BLUE_BOTTOM))
    draw = ImageDraw.Draw(image, "RGBA")

    for y in range(WORK_SIZE):
        t = y / (WORK_SIZE - 1)
        color = lerp(BLUE_TOP, BLUE_BOTTOM, t)
        draw.line([(0, y), (WORK_SIZE, y)], fill=rgba(color))

    highlight = Image.new("RGBA", image.size, (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight, "RGBA")
    highlight_draw.ellipse(
        [u(-80), u(-110), u(410), u(390)],
        fill=(255, 255, 255, 24),
    )
    image.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(u(54))))

    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade, "RGBA")
    shade_draw.rectangle([0, 0, WORK_SIZE, u(72)], fill=(0, 40, 55, 32))
    shade_draw.rectangle([0, u(440), WORK_SIZE, WORK_SIZE], fill=(0, 29, 40, 42))
    image.alpha_composite(shade.filter(ImageFilter.GaussianBlur(u(30))))

    return image


def draw_tilework(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    gold = rgba(GOLD, 170)
    gold_soft = rgba(GOLD, 82)
    blue_line = rgba((67, 171, 187), 72)

    outer = [(256, 34), (478, 256), (256, 478), (34, 256), (256, 34)]
    middle = [(256, 72), (440, 256), (256, 440), (72, 256), (256, 72)]
    draw.line(pxy(outer), fill=gold, width=u(2.2), joint="curve")
    draw.line(pxy(middle), fill=gold_soft, width=u(2), joint="curve")

    stepped = [
        (256, 76),
        (314, 134),
        (398, 134),
        (398, 198),
        (456, 256),
        (398, 314),
        (398, 398),
        (314, 398),
        (256, 456),
        (198, 398),
        (114, 398),
        (114, 314),
        (56, 256),
        (114, 198),
        (114, 134),
        (198, 134),
        (256, 76),
    ]
    draw.line(pxy(stepped), fill=blue_line, width=u(4), joint="curve")
    inset = [(256, 112), (400, 256), (256, 400), (112, 256), (256, 112)]
    draw.line(pxy(inset), fill=rgba((105, 188, 199), 54), width=u(2), joint="curve")

    for center in ((256, 48), (464, 256), (256, 464), (48, 256)):
        draw_diamond(draw, center, 9, fill=rgba(GOLD, 230))
        draw_diamond(draw, center, 4.2, fill=rgba((255, 235, 166), 230))

    for center in ((160, 112), (352, 112), (160, 400), (352, 400)):
        draw_diamond(draw, center, 3.4, fill=rgba(GOLD, 110))


def shadow_from_mask(mask: Image.Image, *, alpha: float, blur: float) -> Image.Image:
    blurred = mask.filter(ImageFilter.GaussianBlur(u(blur)))
    shadow = Image.new("RGBA", mask.size, rgba(BLUE_INK, 0))
    shadow.putalpha(blurred.point(lambda value: round(value * alpha)))
    return shadow


def draw_bubble(image: Image.Image) -> None:
    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([u(96), u(110), u(372), u(296)], radius=u(46), fill=255)
    mask_draw.polygon(pxy([(140, 286), (140, 384), (212, 292)]), fill=255)
    image.alpha_composite(shadow_from_mask(mask, alpha=0.27, blur=8))

    fill = Image.new("RGBA", image.size, rgba(WHITE, 0))
    fill.putalpha(mask)
    fill_draw = ImageDraw.Draw(fill, "RGBA")
    fill_draw.rounded_rectangle([u(96), u(110), u(372), u(296)], radius=u(46), fill=rgba(WHITE))
    fill_draw.polygon(pxy([(140, 286), (140, 384), (212, 292)]), fill=rgba(WHITE))
    image.alpha_composite(fill)

    draw = ImageDraw.Draw(image, "RGBA")
    for cx in (166, 226, 286):
        draw.ellipse([u(cx - 16), u(187 - 16), u(cx + 16), u(187 + 16)], fill=rgba(BLUE_DEEP))


def draw_magnifier(image: Image.Image) -> None:
    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([u(228), u(224), u(410), u(406)], fill=255)
    mask_draw.line([u(382), u(378), u(428), u(424)], fill=255, width=u(34))
    mask_draw.ellipse([u(382 - 17), u(378 - 17), u(382 + 17), u(378 + 17)], fill=255)
    mask_draw.ellipse([u(428 - 17), u(424 - 17), u(428 + 17), u(424 + 17)], fill=255)
    image.alpha_composite(shadow_from_mask(mask, alpha=0.34, blur=7))

    draw = ImageDraw.Draw(image, "RGBA")
    draw_round_line(draw, (382, 378), (428, 424), width=34, fill=rgba(WHITE))
    draw.ellipse([u(226), u(222), u(412), u(408)], fill=rgba(WHITE))
    draw.ellipse([u(252), u(248), u(386), u(382)], fill=rgba(BLUE_DEEP))

    draw_rosette(draw, 319, 315)


def draw_rosette(draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
    gold = rgba(GOLD, 245)
    gold_soft = rgba(GOLD_DARK, 210)
    white = rgba(WHITE, 248)

    draw.line(
        pxy([(cx, cy - 60), (cx + 60, cy), (cx, cy + 60), (cx - 60, cy), (cx, cy - 60)]),
        fill=gold_soft,
        width=u(4),
        joint="curve",
    )
    draw.rectangle([u(cx - 43), u(cy - 43), u(cx + 43), u(cy + 43)], outline=gold, width=u(4))
    draw.line(
        pxy(
            [
                (cx - 50, cy - 50),
                (cx + 50, cy - 50),
                (cx + 50, cy + 50),
                (cx - 50, cy + 50),
                (cx - 50, cy - 50),
            ]
        ),
        fill=rgba(GOLD, 130),
        width=u(2),
        joint="curve",
    )

    rosette = [
        (cx, cy - 52),
        (cx + 14, cy - 36),
        (cx + 38, cy - 36),
        (cx + 38, cy - 12),
        (cx + 54, cy),
        (cx + 38, cy + 12),
        (cx + 38, cy + 38),
        (cx + 14, cy + 38),
        (cx, cy + 54),
        (cx - 14, cy + 38),
        (cx - 38, cy + 38),
        (cx - 38, cy + 12),
        (cx - 54, cy),
        (cx - 38, cy - 12),
        (cx - 38, cy - 36),
        (cx - 14, cy - 36),
        (cx, cy - 52),
    ]
    draw.line(pxy(rosette), fill=white, width=u(7), joint="curve")
    inner_rosette = [(x * 0.76 + cx * 0.24, y * 0.76 + cy * 0.24) for x, y in rosette]
    draw.line(pxy(inner_rosette), fill=rgba(GOLD, 170), width=u(2), joint="curve")

    for center in ((cx, cy - 68), (cx + 68, cy), (cx, cy + 68), (cx - 68, cy)):
        draw_diamond(draw, center, 8.5, fill=gold)
        draw_diamond(draw, center, 3.8, fill=rgba((255, 240, 176), 250))

    draw_round_line(draw, (cx - 27, cy + 5), (cx - 6, cy + 26), width=14, fill=rgba(BLUE_INK, 210))
    draw_round_line(draw, (cx - 6, cy + 26), (cx + 36, cy - 24), width=14, fill=rgba(BLUE_INK, 210))
    draw_round_line(draw, (cx - 27, cy + 5), (cx - 6, cy + 26), width=10, fill=gold)
    draw_round_line(draw, (cx - 6, cy + 26), (cx + 36, cy - 24), width=10, fill=gold)


def draw_master() -> Image.Image:
    image = draw_background()
    draw_tilework(image)
    draw_bubble(image)
    draw_magnifier(image)
    return image.resize((BASE_SIZE, BASE_SIZE), Image.Resampling.LANCZOS)


SVG_TEXT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <title>Avvalo</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="512" y2="512" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#008aa8"/>
      <stop offset="1" stop-color="#00445d"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="9" flood-color="#003f53" flood-opacity="0.3"/>
    </filter>
  </defs>
  <rect width="512" height="512" fill="url(#bg)"/>
  <g fill="none" stroke="#d9ad3a" stroke-width="2.5" stroke-opacity="0.65">
    <path d="M256 34 478 256 256 478 34 256Z"/>
    <path d="M256 72 440 256 256 440 72 256Z" stroke-opacity="0.45"/>
    <path d="M256 76 314 134H398V198L456 256 398 314V398H314L256 456 198 398H114V314L56 256 114 198V134H198Z" stroke="#43abbc" stroke-opacity="0.28" stroke-width="4"/>
  </g>
  <g fill="#d9ad3a">
    <path d="M256 39 265 48 256 57 247 48Z"/>
    <path d="M464 247 473 256 464 265 455 256Z"/>
    <path d="M256 455 265 464 256 473 247 464Z"/>
    <path d="M48 247 57 256 48 265 39 256Z"/>
  </g>
  <g filter="url(#shadow)">
    <path d="M96 156Q96 110 142 110H326Q372 110 372 156V250Q372 296 326 296H212L140 384V296Q96 296 96 250Z" fill="#fffffa"/>
    <g fill="#00485c">
      <circle cx="166" cy="187" r="16"/>
      <circle cx="226" cy="187" r="16"/>
      <circle cx="286" cy="187" r="16"/>
    </g>
    <path d="M382 378 428 424" stroke="#fffffa" stroke-width="34" stroke-linecap="round"/>
    <circle cx="319" cy="315" r="93" fill="#fffffa"/>
    <circle cx="319" cy="315" r="67" fill="#00485c"/>
    <g fill="none" stroke-linecap="round" stroke-linejoin="round">
      <path d="M319 255 379 315 319 375 259 315Z" stroke="#ab7e25" stroke-width="4"/>
      <rect x="276" y="272" width="86" height="86" stroke="#d9ad3a" stroke-width="4"/>
      <path d="M319 263 333 279H357V303L373 315 357 327V353H333L319 369 305 353H281V327L265 315 281 303V279H305Z" stroke="#fffffa" stroke-width="7"/>
      <path d="M292 320 313 341 355 291" stroke="#d9ad3a" stroke-width="10"/>
    </g>
  </g>
</svg>
"""


def render(master: Image.Image, size: int) -> Image.Image:
    """Resize the master square icon to a square RGBA image."""

    return master.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    master = draw_master()
    (STATIC_DIR / "icon.svg").write_text(SVG_TEXT, encoding="utf-8")
    print(f"wrote {STATIC_DIR / 'icon.svg'}")

    for name, size in PNG_OUTPUTS.items():
        render(master, size).save(STATIC_DIR / name, format="PNG")
        print(f"wrote {STATIC_DIR / name} ({size}x{size})")

    largest, *smaller = (render(master, size) for size in ICO_SIZES)
    largest.save(
        STATIC_DIR / "favicon.ico",
        format="ICO",
        append_images=smaller,
        sizes=[(size, size) for size in ICO_SIZES],
    )
    print(f"wrote {STATIC_DIR / 'favicon.ico'} ({', '.join(str(size) for size in ICO_SIZES)})")


if __name__ == "__main__":
    main()
