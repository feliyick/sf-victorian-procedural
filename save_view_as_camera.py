# save_view_as_camera.py — turn whatever you're looking at in the viewport into a named camera in /stage.
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/save_view_as_camera.py', encoding='utf-8').read())
# Asks for a name (e.g. "elevated"), creates/updates /stage/sfh_cam_<name> with prim /cameras/cam_<name>,
# copying the viewport's position, rotation and lens. It joins the camera chain before shot_cam.
import hou
sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
vp = sv.curViewport()
ok, name = hou.ui.readInput('Name for this camera (cam_<name>):', buttons=('Save', 'Cancel'), initial_contents='elevated')
if ok == 0 and name.strip():
    name = name.strip().replace(' ', '_')
    stage = hou.node('/stage')
    xf = vp.viewTransform()
    parts = xf.explode(rotate_order='xyz')
    c = stage.node('sfh_cam_' + name)
    if c is None:
        c = stage.createNode('camera', 'sfh_cam_' + name)
        shot = stage.node('sfh_shot_cam')
        c.setInput(0, shot.inputs()[0]); shot.setInput(0, c)
        c.setPosition(shot.position() + hou.Vector2(2, 0.5))
    c.parmTuple('t').set(tuple(parts['translate'])); c.parmTuple('r').set(tuple(parts['rotate']))
    c.parm('primpath').set('/cameras/cam_' + name)
    try:
        cam = vp.defaultCamera()
        c.parm('focalLength').set(cam.focalLength()); c.parm('horizontalAperture').set(cam.aperture())
    except Exception:
        pass
    if c.parm('fStop'): c.parm('fStop').set(8.0)
    print('saved /cameras/cam_%s  at %s' % (name, tuple(round(v, 2) for v in parts['translate'])))
