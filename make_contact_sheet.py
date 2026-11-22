# make_contact_sheet.py: tile the main web shots into web/contact_sheet.jpg (2 columns, labelled).
# Usage: python make_contact_sheet.py [web_dir]     (needs pillow; run after exr2web.py)
import os, sys
from PIL import Image, ImageDraw, ImageFont

WEB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'render', 'portfolio', 'web')
ORDER = ['sunny_cam_front', 'golden_cam_front', 'night_cam_front', 'sunny_cam_street',
         'sunny_cam_tele', 'golden_cam_wide', 'golden_cam_aerial', 'golden_cam_row_down',
         'night_cam_wide', 'night_cam_row_up']
COLS, TILE_W, GAP, BG = 2, 640, 4, (16, 16, 16)

names = [n for n in ORDER if os.path.exists(os.path.join(WEB, n + '.png'))]
tiles = []
for n in names:
    im = Image.open(os.path.join(WEB, n + '.png')).convert('RGB')
    tiles.append((n, im.resize((TILE_W, round(im.height * TILE_W / im.width)), Image.LANCZOS)))
rows = [tiles[i:i + COLS] for i in range(0, len(tiles), COLS)]
heights = [max(t[1].height for t in r) for r in rows]
W = COLS * TILE_W + (COLS - 1) * GAP
H = sum(heights) + (len(rows) - 1) * GAP
sheet = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default()
y = 0
for r, h in zip(rows, heights):
    for c, (n, im) in enumerate(r):
        x = c * (TILE_W + GAP)
        sheet.paste(im, (x, y))
        draw.text((x + 7, y + 5), n, fill=(0, 0, 0), font=font)
        draw.text((x + 6, y + 4), n, fill=(255, 255, 255), font=font)
    y += h + GAP
out = os.path.join(WEB, 'contact_sheet.jpg')
sheet.save(out, quality=90)
print(out, sheet.size, '%d shots' % len(names))
