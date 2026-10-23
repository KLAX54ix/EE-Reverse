import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def main(path, out, step=50):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
    for x in range(0, w, step):
        d.line([(x,0),(x,h)], fill=(255,80,80), width=1)
        d.text((x+2, 2), str(x), fill=(255,0,0), font=font)
        d.text((x+2, h-14), str(x), fill=(255,0,0), font=font)
    for y in range(0, h, step):
        d.line([(0,y),(w,y)], fill=(80,80,255), width=1)
        d.text((2, y+2), str(y), fill=(0,0,255), font=font)
        d.text((w-30, y+2), str(y), fill=(0,0,255), font=font)
    im.save(out)
    print("saved", out, im.size)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 50)
