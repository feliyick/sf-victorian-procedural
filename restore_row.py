# restore_row.py: puts the hero seed + Row Count back to what they were before preview_gallery_cam.py.
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/restore_row.py', encoding='utf-8').read())
import hou
NET = hou.node('/obj/sf_house_geometry')
if hasattr(hou.session, 'gallery_saved'):
    seed, rows, editable, look, clouds, night = hou.session.gallery_saved
    C = NET.node('STREET_CONTROLS')
    NET.node('victorian_house').parm('seed').set(seed); C.parm('row_count').set(rows); C.parm('editable').set(editable)
    hou.node('/stage/sfh_look').parm('input').set(look); C.parm('clouds').set(clouds); C.parm('night_sky').set(night)
    del hou.session.gallery_saved
    print('restored seed %d, row count %d' % (seed, rows))
else:
    print('nothing to restore')
if hasattr(hou.session, 'gallery_res'):
    k = hou.node('/stage/sfh_karma_render'); k.parm('resolutionx').set(hou.session.gallery_res[0]); k.parm('resolutiony').set(hou.session.gallery_res[1])
    del hou.session.gallery_res; print('render resolution restored')
