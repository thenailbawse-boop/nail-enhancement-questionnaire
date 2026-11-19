import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
out = sys.argv[1]
F = "/root/vibe-editing/plugins/vibe-editing/skills/caption-clips/fonts/Montserrat-ExtraBold.ttf"
PINK, WHITE = (0xF4, 0xA6, 0xC4, 255), (255, 255, 255, 255)
TOP = 300            # below the app's top buttons, above every face
# (start, end, lines, align, max width)
CARDS = [
    (0.3, 4.0,  [[("POV: YOU PULLED UP TO", 0)], [("BLACK BEAUTY BLOCK PARTY", 1)]], "c", 780),
    (4.55, 6.5, [[("PINK", 1), ("EVERYWHERE.", 0)]], "c", 780),
    (6.5, 8.45, [[("BEAUTY PROS", 1)], [("EVERYWHERE.", 0)]], "c", 780),
    (8.6, 13.0, [[("THEN THE", 0)], [("MASTERCLASS", 1), ("STARTED", 0)]], "c", 780),
    (13.0, 18.0,[[("THE HISTORY OF", 0)], [("BLACK BEAUTY", 1)]], "c", 780),
    (18.0, 23.5,[[("YOUR SKILLS ARE", 0)], [("THE", 0), ("BUSINESS", 1)]], "c", 780),
    (23.65, 28.1,[[("AND THE FOOD?", 0)], [("PINK TACOS.", 1)]], "c", 780),
    (28.25, 30.07,[[("BUILD FROM", 0)], [("WHAT YOU", 0)], [("KNOW.", 1)]], "r", 380),
]
for i, (s, e, lines, align, maxw) in enumerate(CARDS):
    txt = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    shadow = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    # one size for the whole card: the biggest that fits every line, at most 70
    size = 70
    while size > 40:
        f = ImageFont.truetype(F, size); gap = d.textlength(" ", font=f)
        if all(sum(d.textlength(t, font=f) for t, _ in L) + gap * (len(L) - 1) <= maxw for L in lines): break
        size -= 2
    lh = int(size * 1.2)
    for k, L in enumerate(lines):
        widths = [d.textlength(t, font=f) for t, _ in L]
        w = sum(widths) + gap * (len(L) - 1)
        x = (1080 - w) / 2 if align == "c" else 940 - w
        y = TOP + k * lh
        for (t, p), ww in zip(L, widths):
            sd.text((x, y + 5), t, font=f, fill=(0, 0, 0, 200), stroke_width=8, stroke_fill=(0, 0, 0, 200))
            d.text((x, y), t, font=f, fill=PINK if p else WHITE, stroke_width=5, stroke_fill=(10, 10, 12, 255))
            x += ww + gap
    Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), txt).save(os.path.join(out, f"w{i}.png"))
    print(f"{i} {s} {e}")
