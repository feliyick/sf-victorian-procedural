# reload_materials.py: re-read materials/house_materials.mtlx into /stage after it changes.
#   exec(open(hou.text.expandString('$HIP/reload_materials.py'), encoding='utf-8').read())
import hou
n = hou.node('/stage/sfh_mtlx')
if n is None:
    print('No /stage/sfh_mtlx node found.')
else:
    if n.parm('reload') is not None:
        n.parm('reload').pressButton()
    hou.hscript('glcache -c')
    n.cook(force=True)
    print('materials reloaded from', n.parm('filepath1').eval())
