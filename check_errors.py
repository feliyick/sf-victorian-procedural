# check_errors.py: READ-ONLY. Re-cooks the house and the /stage network and lists any node that
# still has an error (red triangles in the network editor can be left over from an earlier failure).
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/check_errors.py', encoding='utf-8').read())
import hou
asset = hou.node('/obj/sf_house_geometry/victorian_house')
out = hou.node('/obj/sf_house_geometry/OUT_RENDER')
for n in (asset, out):
    try: n.cook(force=True)
    except hou.OperationFailed: pass
bad = [(n.path(), n.errors()) for n in asset.allSubChildren() if n.errors()]
for n in hou.node('/stage').children():
    try: n.cook(force=True)
    except hou.OperationFailed: pass
    if n.errors(): bad.append((n.path(), n.errors()))
if not bad:
    print('No errors anywhere. Faces in the house:', len(out.geometry().prims()))
    print('porch detail faces:', len(asset.node('porch_detail').geometry().prims()))
else:
    for path, errs in bad:
        print(path); [print('   ', e[:300]) for e in errs]
