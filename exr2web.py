# exr2web.py: Karma EXR (linear) -> sRGB PNG (lossless, 8-bit) + JPG (web, q92).
# Plain sRGB display transform (matches the Karma viewport) with a soft roll-off above 0.85 so lamp/window
# highlights don't clip hard.
import sys, os, numpy as np, OpenEXR
from PIL import Image
def srgb(x):
    x = np.clip(x, 0, None)
    k = 0.85; x = np.where(x > k, k + (1 - k) * np.tanh((x - k) / (1 - k)), x)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)
for src in sys.argv[2:]:
    px = OpenEXR.File(src).channels()['RGBA'].pixels.astype(np.float32)
    img = (np.clip(srgb(px[..., :3]), 0, 1) * 255 + 0.5).astype(np.uint8)
    parts = src.split('/'); look, cam = parts[-2], os.path.splitext(parts[-1])[0]
    base = os.path.join(sys.argv[1], '%s_%s' % (look, cam))
    Image.fromarray(img).save(base + '.png', optimize=True)
    Image.fromarray(img).save(base + '.jpg', quality=92, subsampling=0)
    print(base, img.shape)
