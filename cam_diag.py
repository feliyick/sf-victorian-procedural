# cam_diag.py: read-only. Prints what USD actually has for cam_gallery vs cam_front.
#   exec(open(hou.text.expandString('$HIP/cam_diag.py'), encoding='utf-8').read())
import hou
st = hou.node('/stage/sfh_karma_render').stage()
for name in ('cam_gallery', 'cam_front'):
    p = st.GetPrimAtPath('/cameras/' + name)
    print(name, {a: p.GetAttribute(a).Get() for a in ('focalLength', 'horizontalAperture', 'verticalAperture',
          'horizontalApertureOffset', 'verticalApertureOffset', 'clippingRange', 'projection') if p.GetAttribute(a)})
    n = hou.node('/stage/sfh_' + name)
    print('   node parms:', {q.name(): q.eval() for q in n.parms() if any(k in q.name().lower() for k in ('aperture', 'focal', 'aspect', 'resolution', 'conform'))})
