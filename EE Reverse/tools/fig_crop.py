import sys
from PIL import Image, ImageDraw, ImageFont

def main(path, out, x0, y0, x1, y1, step=20, scale=2):
    im = Image.open(path).convert('RGB')
    crop = im.crop((x0, y0, x1, y1))
    w, h = crop.size
    crop = crop.resize((w*scale, h*scale), Image.NEAREST)
    d = ImageDraw.Draw(crop)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
    for gx in range(0, x1-x0+1, step):
        X = gx*scale
        d.line([(X,0),(X,h*scale)], fill=(255,120,120), width=1)
        d.text((X+2, 2), str(x0+gx), fill=(200,0,0), font=font)
    for gy in range(0, y1-y0+1, step):
        Y = gy*scale
        d.line([(0,Y),(w*scale,Y)], fill=(120,120,255), width=1)
        d.text((2, Y+2), str(y0+gy), fill=(0,0,200), font=font)
    crop.save(out)
    print("saved", out, crop.size)

if __name__ == '__main__':
    a = sys.argv
    main(a[1], a[2], int(a[3]), int(a[4]), int(a[5]), int(a[6]),
         int(a[7]) if len(a)>7 else 20, int(a[8]) if len(a)>8 else 2)
