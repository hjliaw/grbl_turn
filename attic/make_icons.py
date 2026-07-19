"""Regenerate the app icons in grbl_turn/resources/icons/ from logo.svg.

Needs inkscape and Pillow (dev-only: `.venv/bin/pip install pillow`);
the .icns step needs macOS's iconutil and is skipped elsewhere.

    .venv/bin/python attic/make_icons.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
LOGO = REPO / "grbl_turn" / "resources" / "images" / "logo.svg"
OUT = REPO / "grbl_turn" / "resources" / "icons"
MARGIN = 0.07   # transparent border on each side of the square canvas

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
PNG_SIZES = [128, 256, 512]
ICONSET = {  # iconutil filename -> pixel size
    "icon_16x16": 16, "icon_16x16@2x": 32,
    "icon_32x32": 32, "icon_32x32@2x": 64,
    "icon_128x128": 128, "icon_128x128@2x": 256,
    "icon_256x256": 256, "icon_256x256@2x": 512,
    "icon_512x512": 512, "icon_512x512@2x": 1024,
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw = tmp / "logo.png"
        subprocess.run(
            ["inkscape", str(LOGO), "--export-area-drawing",
             "--export-type=png", "--export-height=1024",
             f"--export-filename={raw}"],
            check=True)

        art = Image.open(raw).convert("RGBA")
        side = round(max(art.size) / (1 - 2 * MARGIN))
        master = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        master.paste(art, ((side - art.width) // 2, (side - art.height) // 2))

        def at(px: int) -> Image.Image:
            return master.resize((px, px), Image.LANCZOS)

        for px in PNG_SIZES:
            at(px).save(OUT / f"grbl_turn-{px}.png")
        at(1024).save(OUT / "grbl_turn.ico",
                      sizes=[(s, s) for s in ICO_SIZES])

        if shutil.which("iconutil"):
            iconset = tmp / "grbl_turn.iconset"
            iconset.mkdir()
            for name, px in ICONSET.items():
                at(px).save(iconset / f"{name}.png")
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset),
                 "-o", str(OUT / "grbl_turn.icns")],
                check=True)
        else:
            print("iconutil not found (not macOS) — skipped .icns")

    for f in sorted(OUT.iterdir()):
        print(f"{f.relative_to(REPO)}  {f.stat().st_size} bytes")


if __name__ == "__main__":
    main()
