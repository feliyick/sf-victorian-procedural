# render_all.py: one unattended run - the 9 gallery houses (portrait) THEN the 10 main shots, final quality.
# ~55-60 min. Output: render/portfolio/<time>/gallery/ and beauty/<look>/
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/render_all.py', encoding='utf-8').read())
import hou, os
HIP = hou.text.expandString('$HIP')
src = open(os.path.join(HIP, 'capture_portfolio.py'), encoding='utf-8').read()
for k in ('DO_CLAY', 'DO_GL', 'DO_WIRE', 'DO_SWEEPS', 'DO_BUILD'):
    src = src.replace('\n%s = True' % k.ljust(9), '\n%s = False' % k.ljust(9))
src = src.replace('DO_GALLERY = False', 'DO_GALLERY = True')
src = src.replace('GALLERY_SEEDS = [3, 11, 27, 42, 58, 77, 101, 133, 150, 188, 215, 240, 271, 305, 333, 360]',
                  'GALLERY_SEEDS = [22, 290, 468, 354, 202, 151, 500, 480, 222]')
hou.hipFile.save()
exec(src)
