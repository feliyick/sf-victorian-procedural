# pick_seeds.py: quick low-res Karma snapshots (360 px, 32 samples; the viewport capture ignored the lens) of the hero house alone for seeds 1..48 (no Karma), so you can pick
# favourites for the gallery. Output: render/portfolio/<time>/gallery_gl/seed_###.png  (~5-10 min)
#   exec(open(hou.text.expandString('$HIP/pick_seeds.py'), encoding='utf-8').read())
import hou, os
HIP = hou.text.expandString('$HIP')
SHOTS_OVERRIDE = []
src = open(os.path.join(HIP, 'capture_portfolio.py'), encoding='utf-8').read()
for k in ('DO_BEAUTY', 'DO_CLAY', 'DO_GL', 'DO_WIRE', 'DO_SWEEPS', 'DO_BUILD'):
    src = src.replace('\n%s = True' % k.ljust(9), '\n%s = False' % k.ljust(9))
src = src.replace('DO_GALLERY = False', 'DO_GALLERY = True').replace('GALLERY_GL = True', 'GALLERY_GL = False')
src = src.replace('QUICK     = False', 'QUICK     = True').replace('GALLERY_RES = (720, 720)', 'GALLERY_RES = (360, 360)')
src = src.replace('GALLERY_SEEDS = [3, 11, 27, 42, 58, 77, 101, 133, 150, 188, 215, 240, 271, 305, 333, 360]', 'GALLERY_SEEDS = list(range(1, 49))')
exec(src)
