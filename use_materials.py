# use_materials.py: point /stage at a NEW material file version (no hot-reload, so no USD cache problems).
#   exec(open(hou.text.expandString('$HIP/use_materials.py'), encoding='utf-8').read())
# Each time the materials change, Claude writes house_materials_vN.mtlx; this picks the newest one.
import hou, glob, os, re
files = glob.glob(hou.text.expandString('$HIP/materials/house_materials_v*.mtlx'))
newest = max(files, key=lambda f: int(re.search(r'_v(\d+)\.mtlx$', f).group(1)))
hou.node('/stage/sfh_mtlx').parm('filepath1').set('$HIP/materials/' + os.path.basename(newest))
print('now using', os.path.basename(newest), '- press restart render in the Karma viewport')
