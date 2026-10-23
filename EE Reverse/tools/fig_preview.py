import sys
from PIL import Image, ImageDraw, ImageFont

# canvas coords -> fig07 pixel coords:  px=(cx-17125)/45, py=(cy-1385)/45
OX, OY, S = 17125, 1385, 45.0
def P(cx, cy):
    return ((cx-OX)/S, (cy-OY)/S)

solid = [
    [(17125,19025),(43675,19025)],
    [(33595,28970),(33595,1970)],
    [(37060,22040),(36790,25145),(40615,20915),(37060,22040)],
    [(26215,3770),(26215,11555),(18790,15065),(26215,3770)],
    [(43675,19025),(42975,18725)],
    [(43675,19025),(42975,19325)],
    [(33595,1970),(33295,2670)],
    [(33595,1970),(33895,2670)],
]
dashed = [
    [(26215,11555),(33595,19025)],
    [(33595,19025),(37060,22040)],
    [(26215,3770),(33595,19025)],
    [(33595,19025),(36790,25145)],
    [(18790,15065),(33595,19025)],
    [(33595,19025),(40615,20915)],
]
labels = [("E",26350,2735),("D",26125,12725),("F",17710,14570),("O",32650,20195),
          ("A",37240,20645),("B",36475,26900),("C",42010,20825),("x",42775,19475),("y",32335,2285)]

def dashline(d, p1, p2, on=14, off=9):
    import math
    x1,y1 = p1; x2,y2 = p2
    L = math.hypot(x2-x1, y2-y1)
    n = int(L//(on+off))+1
    ux, uy = (x2-x1)/L, (y2-y1)/L
    for i in range(n):
        s = i*(on+off); e = min(s+on, L)
        d.line([(x1+ux*s, y1+uy*s), (x1+ux*e, y1+uy*e)], fill=0, width=2)

def main(out):
    im = Image.new('L', (602, 620), 255)
    d = ImageDraw.Draw(im)
    for p in solid:
        d.line([P(x,y) for x,y in p], fill=0, width=2)
    for p in dashed:
        dashline(d, P(*p[0]), P(*p[1]))
    try:
        font = ImageFont.truetype("timesi.ttf", 22)
    except Exception:
        try: font = ImageFont.truetype("times.ttf", 22)
        except Exception: font = ImageFont.load_default()
    for t, cx, cy in labels:
        x, y = P(cx, cy)
        d.text((x, y-10), t, fill=0, font=font)
    # side by side with original
    orig = Image.open(r'D:\EE Reverse\captures\paper-figs\fig07.png').convert('L')
    combo = Image.new('L', (602*2+20, 620), 255)
    combo.paste(orig, (0,0))
    combo.paste(im, (602+20, 0))
    combo.save(out)
    print("saved", out, combo.size)

if __name__ == '__main__':
    main(sys.argv[1])
