"""
export_scene_metrics.py - per-seed scene JSON for the robotics side (hython, never saves the scene):

    hython export_scene_metrics.py [seed seed ...]      -> render/scene_metrics/seed_N.json

For each hero seed (the row follows it) it runs houdini-mcp's scene_metrics on the labelled street geometry:
per house walls/door/stairs/porch boxes, the exact stair layout from the asset (risers, treads, riser_m, tread_m,
tread_heights_y bottom step first, landing_y = door sill, landing_top_y, landing_depth_m, entry_type) and the
doorbell (box, normal, press_point, mount, finish). Metres, Y up, facade toward +Z.
"""
import os, sys, json
HIP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/HoudiniProjects/houdini-mcp'))
import hou
SEEDS = [int(s) for s in sys.argv[1:]] or [22, 3, 11, 27, 42, 58, 77, 101, 150, 202, 5, 8, 14, 19, 31, 36, 47, 63, 70, 88, 95,
                                           120, 133, 177, 222, 290]
hou.hipFile.load(os.path.join(HIP, 'SanFranciscoHouse_v4_hda.hipnc'), suppress_save_prompt=True, ignore_load_warnings=True)
from houdini_mcp import houdini_listener as L
L.OVERRIDES.update({'auto_save': False, 'headless_allow_save': False, 'allow_reload': False}); L.load_config()
out = os.path.join(HIP, 'render', 'scene_metrics'); os.makedirs(out, exist_ok=True)
seed = hou.parm('/obj/sf_house_geometry/victorian_house/seed')
summary = []
for s in SEEDS:
    seed.set(s)
    m = L.cmd_scene_metrics()
    json.dump(m, open(os.path.join(out, 'seed_%d.json' % s), 'w'), indent=1)
    for hid, h in sorted(m['houses'].items(), key=lambda kv: int(kv[0])):
        st = h.get('stairs') or {}
        summary.append({'seed': s, 'house': int(hid), 'entry': st.get('entry_type'), 'risers': st.get('risers'),
                        'riser_m': st.get('riser_m'), 'tread_m': st.get('tread_m'), 'climb_m': st.get('climb_m'),
                        'doorbell': bool(h.get('doorbell')), 'mount': (h.get('doorbell') or {}).get('mount')})
    print('seed', s, 'houses', len(m['houses']), flush=True)
json.dump(summary, open(os.path.join(out, 'summary.json'), 'w'), indent=1)
