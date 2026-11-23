# dump_door_debug.py: READ-ONLY. Saves the geometry around the front door to debug/door_debug.json
# so Claude can see the clipping offline.
#   exec(open(hou.text.expandString('$HIP/dump_door_debug.py'), encoding='utf-8').read())
import hou, json, os
a = hou.node('/obj/sf_house_geometry/victorian_house')
out = {'nodes': sorted(n.name() for n in a.children())}
bp = a.node('building_params').geometry()
for at in bp.globalAttribs():
    out[at.name()] = bp.attribValue(at.name())
out['slots'] = [{at.name(): (list(p.attribValue(at.name())) if at.size() > 1 else p.attribValue(at.name()))
                 for at in bp.pointAttribs()} for p in bp.points()]
for nm in ('entry_params', 'stair_params'):
    n = a.node(nm)
    if not n: continue
    g = n.geometry()
    out[nm] = {at.name(): g.attribValue(at.name()) for at in g.globalAttribs()}
    out[nm + '_pts'] = [{at.name(): (list(p.attribValue(at.name())) if at.size() > 1 else p.attribValue(at.name()))
                         for at in g.pointAttribs()} for p in g.points()]
doors = [s for s in out['slots'] if s.get('name') in ('door', 'stairs', 'entry')]
x0 = min(s['bbmin'][0] for s in doors) - 2.0 if doors else -99
x1 = max(s['bbmax'][0] for s in doors) + 2.0 if doors else 99
geo = hou.node('/obj/sf_house_geometry/OUT_RENDER').geometry()
prims = []
for pr in geo.prims():
    pts = [list(v.point().position()) for v in pr.vertices()]
    if not pts: continue
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    if max(xs) < x0 or min(xs) > x1 or min(ys) > 5.0: continue
    d = {'pts': pts, 'groups': [g.name() for g in pr.groups()]}
    for k in ('paint', 'name'):
        try: d[k] = pr.attribValue(k)
        except hou.OperationFailed: pass
    prims.append(d)
out['prims'] = prims
def safe(o):
    if isinstance(o, dict): return {k: safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [safe(x) for x in o]
    if isinstance(o, (int, float, str)) or o is None: return o
    return str(o)
out = {k: safe(v) for k, v in out.items()}
os.makedirs(hou.text.expandString('$HIP/debug'), exist_ok=True)
path = hou.text.expandString('$HIP/debug/door_debug.json')
json.dump(out, open(path, 'w'))
print('saved', path, ' prims near door:', len(prims))
