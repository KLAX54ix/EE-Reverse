"""Contact sheet of extracted wsd figures, for quick visual triage.

Usage: python fig_sheet.py <figdir> <out.png> [cols] [cell]
Builds a labeled grid; each image is scaled to fit its cell.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont


def main(figdir, out, cols=6, cell=300):
    files = sorted(f for f in os.listdir(figdir)
                   if f.lower().startswith("fig") and f.lower().endswith(".png"))
    cols = int(cols)
    cell = int(cell)
    rows = (len(files) + cols - 1) // cols
    pad = 8
    label_h = 22
    W = cols * (cell + pad) + pad
    H = rows * (cell + label_h + pad) + pad
    sheet = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    for i, f in enumerate(files):
        im = Image.open(os.path.join(figdir, f)).convert("RGB")
        im.thumbnail((cell, cell - label_h), Image.LANCZOS)
        cx = pad + (i % cols) * (cell + pad)
        cy = pad + (i // cols) * (cell + label_h + pad)
        sheet.paste(im, (cx + (cell - im.width) // 2,
                         cy + label_h + (cell - label_h - im.height) // 2))
        tag = f.replace(".png", "")
        d.text((cx + 4, cy + 2), "%s  %dx%d" % (tag, im.width, im.height),
               fill=(180, 0, 0), font=font)
        d.rectangle([cx - 2, cy - 2, cx + cell + 2, cy + cell + 4],
                    outline=(200, 200, 200))
    sheet.save(out)
    print("saved", out, sheet.size, "files:", len(files))


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2],
         int(a[3]) if len(a) > 3 else 6,
         int(a[4]) if len(a) > 4 else 300)
