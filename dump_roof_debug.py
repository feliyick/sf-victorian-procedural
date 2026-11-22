# dump_roof_debug.py: READ-ONLY. Saves the roof inputs/outputs to debug/roof_debug.json so
# Claude can test the roof code offline (and look at the result) instead of guessing.
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/dump_roof_debug.py', encoding='utf-8').read())
import hou, json, os
a = hou.node('/obj/sf_house_geometry/victorian_house')
out = {}
bp = a.node('building_params').geometry()
for k in ('W', 'D', 'building_h', 'style', 'roof_type'):
    out[k] = bp.attribValue(k)
out['slots'] = [{'name': p.attribValue('name'), 'floor': p.attribValue('floor'),
                 'bbmin': list(p.attribValue('bbmin')), 'bbmax': list(p.attribValue('bbmax'))} for p in bp.points()]
ol = a.node('roof_outline').geometry()
out['outline'] = [[list(v.point().position()) for v in pr.vertices()] for pr in ol.prims()]
faces = a.node('roof_outline_faces').geometry()
out['roof_top_faces'] = [[list(v.point().position()) for v in pr.vertices()] for pr in faces.prims()]
rb = a.node('roof_build').geometry()
out['roof_build'] = [{'groups': [g.name() for g in pr.groups()], 'pts': [list(v.point().position()) for v in pr.vertices()]}
                     for pr in rb.prims()][:4000]
os.makedirs(hou.text.expandString('$HIP/debug'), exist_ok=True)
path = hou.text.expandString('$HIP/debug/roof_debug.json')
json.dump(out, open(path, 'w'))
print('saved', path, ' outline polys:', len(out['outline']), ' roof faces:', len(rb.prims()))
