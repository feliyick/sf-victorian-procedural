# sfh_lights (Python LOP): switches the window + street-lamp glow on per look by editing the
# emission of the 'room' and 'lamp' materials directly on the stage. Reads the look from spare parm 'look'
# (= sfh_look's Select Input): 0 golden, 3 dusk, 4 sunny, 5 night.
import hou
node = hou.pwd()
def note(text):
    # node comment = status readout. Only when it changes, and off the undo stack: a cook must never
    # add undo steps or mark the scene unsaved on its own.
    if node.comment() != text:
        with hou.undos.disabler(): node.setComment(text)
stage = node.editableStage()
look = node.evalParm('look')
key = {3: 'dusk', 5: 'night'}.get(look, 'day')
room = node.evalParm('room_' + key)
lamp = node.evalParm('lamp_' + key) if key != 'day' else 0.0
hits = []
for prim in stage.Traverse():
    if prim.GetTypeName() != 'Shader': continue
    a = prim.GetAttribute('inputs:emission')
    if not a or not a.IsValid(): continue
    p = prim.GetParent(); name = None
    while p and p.IsValid() and str(p.GetPath()) != '/':
        if p.GetTypeName() == 'Material': name = p.GetName(); break
        p = p.GetParent()
    if name == 'room': a.Set(float(room)); hits.append(str(prim.GetPath()))
    elif name == 'lamp': a.Set(float(lamp)); hits.append(str(prim.GetPath()))
note('look %s: room %.1f, lamp %.1f  (%d shaders)' % (key, room, lamp, len(hits)))
