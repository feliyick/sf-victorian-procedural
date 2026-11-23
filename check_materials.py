# check_materials.py: READ-ONLY. Lists the materials on the stage and what each house part is bound to.
#   exec(open(hou.text.expandString('$HIP/check_materials.py'), encoding='utf-8').read())
import hou
from pxr import UsdShade
mt = hou.node('/stage/sfh_mtlx')
print('sublayer node errors  :', mt.errors() or 'none')
print('sublayer node warnings:', mt.warnings() or 'none')
stage = hou.node('/stage/sfh_hero_cam').stage()
print('materials on stage:', sorted(str(p.GetPath()) for p in stage.Traverse() if p.GetTypeName() == 'Material'))
for prim in stage.GetPrimAtPath('/house').GetChildren():
    mat = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
    print('  %-16s -> %s' % (prim.GetPath(), mat.GetPath() if mat else 'NOTHING BOUND'))
