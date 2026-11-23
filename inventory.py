# inventory.py — read-only. Prints what each input of merge3 contains, so the
# paint step knows which groups / attributes exist. Changes nothing.
#   exec(open(hou.text.expandString('$HIP/inventory.py'), encoding='utf-8').read())
import hou
NET = hou.node('/obj/sf_house_geometry')
merge3 = NET.node('merge3')
display = NET.displayNode()
print('display node:', display.path())
for i, inp in enumerate(merge3.inputs()):
    if inp is None:
        continue
    geo = inp.geometry()
    print('\n[%d] %s  (%d prims)' % (i, inp.name(), len(geo.prims())))
    print('   prim groups :', ', '.join('%s(%d)' % (g.name(), len(g.prims())) for g in geo.primGroups()) or '-')
    print('   prim attribs:', ', '.join(a.name() for a in geo.primAttribs()) or '-')
    print('   point attribs:', ', '.join(a.name() for a in geo.pointAttribs()) or '-')
    name = geo.findPrimAttrib('name')
    if name and name.dataType() == hou.attribData.String:
        print('   name values :', ', '.join(sorted(set(name.strings()))[:30]))
# what feeds merge3 input 0 side (the wall)
for n in ('boolean_recess', 'boolean2', 'roof_flat_top'):
    node = NET.node(n)
    if node:
        g = node.geometry()
        print('\n%s: %d prims, groups: %s' % (n, len(g.prims()), ', '.join(x.name() for x in g.primGroups()) or '-'))
