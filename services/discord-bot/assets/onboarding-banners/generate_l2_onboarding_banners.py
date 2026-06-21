#!/usr/bin/env python3
"""Generate L2 Systems Discord onboarding banners.

Local deterministic image generator: no external assets, no fake logos,
no noisy AI text. Produces 1600x600 PNG banners with a dark liquid-glass
technical aesthetic aligned to the current L2 server structure.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Pillow is required and was not imported: {exc}")

W, H = 1600, 600
OUT = Path(__file__).resolve().parent
PALETTE = {
    "void": "#050712",
    "indigo": "#11183a",
    "violet": "#7a5cff",
    "cyan": "#00e5ff",
    "ice": "#dcecff",
    "muted": "#6e7c96",
}
CHANNELS = {
    "start-here": {
        "channel_id": "1509401628145619106",
        "title": "START HERE",
        "subtitle": "OPERATIONAL ENTRYPOINT",
        "motif": "entry",
        "accent": (0, 229, 255),
        "secondary": (122, 92, 255),
    },
    "quem-somos": {
        "channel_id": "1509401632809549824",
        "title": "QUEM SOMOS",
        "subtitle": "IDENTITY LAYER",
        "motif": "orbit",
        "accent": (122, 92, 255),
        "secondary": (0, 229, 255),
    },
    "o-que-fazemos": {
        "channel_id": "1509401638983696576",
        "title": "O QUE FAZEMOS",
        "subtitle": "EXECUTION LAYER",
        "motif": "servers",
        "accent": (0, 229, 255),
        "secondary": (166, 120, 255),
    },
    "hierarquia": {
        "channel_id": "1509401643966271539",
        "title": "HIERARQUIA",
        "subtitle": "AUTHORITY + ACCESS MODEL",
        "motif": "hierarchy",
        "accent": (191, 92, 255),
        "secondary": (0, 229, 255),
    },
}
ROLES = [
    "L²",
    "L² ENTERPRENEUR",
    "Systems Engineer",
    "Full Stack Engineer",
    "Product Engineer",
    "Build Engineer",
    "Ops Engineer",
    "Member/@everyone",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def add_gradient(img: Image.Image, accent: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    px = img.load()
    for y in range(H):
        for x in range(W):
            nx, ny = x / W, y / H
            radial1 = max(0, 1 - math.hypot(nx - 0.72, ny - 0.38) * 1.55)
            radial2 = max(0, 1 - math.hypot(nx - 0.20, ny - 0.88) * 1.85)
            base = (5 + int(10 * ny), 7 + int(11 * nx), 18 + int(30 * (1 - ny)))
            r = min(255, base[0] + int(accent[0] * radial1 * 0.23) + int(secondary[0] * radial2 * 0.14))
            g = min(255, base[1] + int(accent[1] * radial1 * 0.23) + int(secondary[1] * radial2 * 0.14))
            b = min(255, base[2] + int(accent[2] * radial1 * 0.23) + int(secondary[2] * radial2 * 0.14))
            px[x, y] = (r, g, b)


def glow_line(layer: Image.Image, pts, color, width=2, blur=8):
    d = ImageDraw.Draw(layer)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(pts, fill=(*color, 90), width=width * 4, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    layer.alpha_composite(glow)
    d.line(pts, fill=(*color, 185), width=width, joint="curve")


def rounded_panel(layer, xy, outline, fill=(10, 14, 32, 218), radius=28):
    """Draw a high-contrast glass panel.

    The first version was too translucent and allowed the bright glow to wash
    out the title area. This version keeps the liquid-glass edge, but anchors
    the content on a dark readable surface.
    """
    d = ImageDraw.Draw(layer)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx1, sy1, sx2, sy2 = xy
    sd.rounded_rectangle((sx1 + 12, sy1 + 20, sx2 + 12, sy2 + 20), radius=radius, fill=(0, 0, 0, 165))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    layer.alpha_composite(shadow)
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=(*outline, 185), width=2)
    # restrained inner highlight; never crosses the text block
    d.line([(sx1 + 30, sy1 + 30), (sx2 - 42, sy1 + 30)], fill=(255, 255, 255, 34), width=1)


def draw_grid(layer, accent):
    d = ImageDraw.Draw(layer)
    for x in range(0, W, 50):
        alpha = 22 if x % 200 else 35
        d.line([(x, 0), (x, H)], fill=(*accent, alpha), width=1)
    for y in range(0, H, 50):
        alpha = 18 if y % 200 else 30
        d.line([(0, y), (W, y)], fill=(*accent, alpha), width=1)


def draw_common_text(layer, cfg):
    d = ImageDraw.Draw(layer)
    f_brand = font(24, True)
    f_title = font(72, True)
    f_sub = font(24, False)
    d.text((92, 84), "L2 SYSTEMS", font=f_brand, fill=(225, 238, 255, 245), spacing=4)
    d.text((92, 132), cfg["title"], font=f_title, fill=(250, 253, 255, 255))
    d.text((96, 224), cfg["subtitle"], font=f_sub, fill=(*cfg["accent"], 255))
    # micro rule lines only, no noisy labels
    d.line([(96, 270), (480, 270)], fill=(*cfg["accent"], 150), width=2)
    d.line([(96, 282), (360, 282)], fill=(*cfg["secondary"], 85), width=1)


def motif_entry(layer, cfg):
    c, s = cfg["accent"], cfg["secondary"]
    for i in range(9):
        y = 110 + i * 48
        glow_line(layer, [(720, y), (950 + i * 18, y + 12), (1210, 300), (1460, 300 + math.sin(i) * 130)], c if i % 2 else s, 2, 10)
    rounded_panel(layer, (900, 140, 1430, 460), c, fill=(10, 14, 32, 130), radius=36)
    d = ImageDraw.Draw(layer)
    for i in range(6):
        x = 960 + i * 78
        d.rounded_rectangle((x, 205, x + 42, 340), radius=12, fill=(*c, 32), outline=(*c, 110), width=1)
        d.ellipse((x + 14, 366, x + 28, 380), fill=(*s, 160))


def motif_orbit(layer, cfg):
    c, s = cfg["accent"], cfg["secondary"]
    d = ImageDraw.Draw(layer)
    center = (1165, 300)
    for r, col, a in [(80, c, 140), (145, s, 110), (225, c, 70), (300, s, 45)]:
        d.ellipse((center[0]-r, center[1]-r, center[0]+r, center[1]+r), outline=(*col, a), width=2)
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        x = center[0] + math.cos(rad) * (145 if ang % 90 else 225)
        y = center[1] + math.sin(rad) * (145 if ang % 90 else 225)
        d.ellipse((x-7, y-7, x+7, y+7), fill=(*c, 190))
        glow_line(layer, [center, (x, y)], s, 1, 7)
    rounded_panel(layer, (1030, 210, 1300, 390), c, fill=(10, 14, 32, 126), radius=34)


def motif_servers(layer, cfg):
    c, s = cfg["accent"], cfg["secondary"]
    d = ImageDraw.Draw(layer)
    for i in range(5):
        x1, y1 = 875 + i * 105, 155 + (i % 2) * 32
        rounded_panel(layer, (x1, y1, x1 + 86, y1 + 270), c if i % 2 else s, fill=(8, 13, 30, 176), radius=18)
        for j in range(5):
            y = y1 + 36 + j * 42
            d.line([(x1+18, y), (x1+68, y)], fill=(*c, 155), width=2)
        d.ellipse((x1+34, y1+222, x1+52, y1+240), fill=(*s, 210))
    for y in [180, 260, 340, 420]:
        glow_line(layer, [(760, y), (860, y), (1395, 300)], c, 1, 8)


def motif_hierarchy(layer, cfg):
    c, s = cfg["accent"], cfg["secondary"]
    d = ImageDraw.Draw(layer)
    nodes = [(1160, 130), (980, 270), (1160, 270), (1340, 270), (900, 430), (1060, 430), (1260, 430), (1420, 430)]
    for p in nodes[1:4]:
        glow_line(layer, [nodes[0], p], c, 2, 8)
    for p in nodes[4:]:
        parent = nodes[1 + (nodes[4:].index(p) % 3)]
        glow_line(layer, [parent, p], s, 1, 7)
    sizes = [28, 21, 21, 21, 15, 15, 15, 15]
    for idx, ((x, y), r) in enumerate(zip(nodes, sizes)):
        col = c if idx == 0 else s if idx < 4 else c
        d.ellipse((x-r, y-r, x+r, y+r), fill=(*col, 55), outline=(*col, 210), width=2)
        d.ellipse((x-4, y-4, x+4, y+4), fill=(236, 248, 255, 220))


def add_noise_and_vignette(img):
    rng = random.Random(2048)
    noise = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    np = noise.load()
    for _ in range(22000):
        x = rng.randrange(W); y = rng.randrange(H); a = rng.randrange(4, 18)
        np[x, y] = (255, 255, 255, a)
    img.alpha_composite(noise)
    vign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vp = vign.load()
    for y in range(H):
        for x in range(W):
            nx = (x - W / 2) / (W / 2); ny = (y - H / 2) / (H / 2)
            a = int(min(150, max(0, (nx*nx + ny*ny - 0.36) * 125)))
            vp[x, y] = (0, 0, 0, a)
    img.alpha_composite(vign)


def generate(name, cfg):
    base = Image.new("RGB", (W, H), PALETTE["void"])
    add_gradient(base, cfg["accent"], cfg["secondary"])
    layer = base.convert("RGBA")
    draw_grid(layer, cfg["accent"])
    rounded_panel(layer, (62, 58, 610, 340), cfg["accent"], fill=(7, 10, 24, 232), radius=34)
    {"entry": motif_entry, "orbit": motif_orbit, "servers": motif_servers, "hierarchy": motif_hierarchy}[cfg["motif"]](layer, cfg)
    draw_common_text(layer, cfg)
    add_noise_and_vignette(layer)
    path = OUT / f"{name}.png"
    layer.convert("RGB").save(path, quality=95, optimize=True)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, cfg in CHANNELS.items():
        path = generate(name, cfg)
        assets.append({
            "name": name,
            "channel_id": cfg["channel_id"],
            "file": str(path).replace("\\", "/"),
            "dimensions": [W, H],
            "title": cfg["title"],
            "subtitle": cfg["subtitle"],
        })
    manifest = {
        "brand": "L2 Systems",
        "style": "dark liquid glass, minimal technical, violet/cyan accents, operational systems aesthetic",
        "palette": PALETTE,
        "server_alignment": {
            "guild_id": "1058835686385532969",
            "roles_reflected": ROLES,
            "permission_copy_principle": "minimum necessary access, role-based operational responsibility, no unsupported claims beyond current role/channel inventory",
        },
        "assets": assets,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
