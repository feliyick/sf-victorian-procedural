# preview_gallery_cam.py: NO rendering, NO capturing - it only shows the house alone and moves cam_gallery
# onto it, exactly as the gallery render will frame it. It asks which seed to frame.
# When you're done looking, run restore_row.py to put Row Count + your original seed back.
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/preview_gallery_cam.py', encoding='utf-8').read())
import hou, os
HIP = hou.text.expandString('$HIP')
NET = hou.node('/obj/sf_house_geometry'); hero = NET.node('victorian_house'); ctl = NET.node('STREET_CONTROLS')
ok, txt = hou.ui.readInput('Which seed do you want to frame?', buttons=('Frame it', 'Cancel'), initial_contents='22')
if ok == 0 and txt.strip().isdigit():
    if hasattr(hou.session, 'gallery_saved') and len(hou.session.gallery_saved) == 2:   # from the older version
        ctl.parm('row_count').set(hou.session.gallery_saved[1]); del hou.session.gallery_saved
    if not hasattr(hou.session, 'gallery_saved'):                       # remember the originals once
        hou.session.gallery_saved = (hero.parm('seed').eval(), ctl.parm('row_count').eval(), ctl.parm('editable').eval(),
                                     hou.node('/stage/sfh_look').parm('input').eval(), ctl.parm('clouds').eval(), ctl.parm('night_sky').eval())
    ctl.parm('row_count').set(1); ctl.parm('editable').set(0)              # procedural row of 1 = the hero house alone
    hou.node('/stage/sfh_look').parm('input').set(4); ctl.parm('clouds').set(1); ctl.parm('night_sky').set(0)   # sunny, like the render
    hero.parm('seed').deleteAllKeyframes(); hero.parm('seed').set(int(txt.strip()))
    src = open(os.path.join(HIP, 'capture_portfolio.py'), encoding='utf-8').read()
    src = src[src.index('def aim_gallery_cam'):src.index('def gl_capture')]
    GALLERY_RES = (720, 960); stage = hou.node('/stage')
    def log(m): print(m)
    exec(src)
    aim_gallery_cam()
    k = hou.node('/stage/sfh_karma_render')                      # the Karma viewport frames to the render resolution
    if not hasattr(hou.session, 'gallery_res'): hou.session.gallery_res = (k.parm('resolutionx').eval(), k.parm('resolutiony').eval())
    k.parm('resolutionx').set(720); k.parm('resolutiony').set(960)
    print('Framing seed %s (portrait 720 x 960). Pick /cameras/cam_gallery; turn on the camera mask to see the exact frame.' % txt.strip())
