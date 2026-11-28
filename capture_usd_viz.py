"""
capture_usd_viz.py - renders that explain the USD structure (hython, in memory only; the .hip is never saved):

    hython capture_usd_viz.py <mode> <camera> <out.exr> [look]
      mode  material    every face coloured by its material subset (= how the stage used to be split: one prim
                        per material)
            object      every object prim its own colour (house_0/door_300, .../window_011 ...); foliage is one
                        PointInstancer, the lamps one shared asset
            instancing  grey scene; foliage coloured by which of the 8 blob prototypes each instance uses, lamp
                        posts (native instances of one asset) pink

A viz material reading displayColor is bound over everything after sfh_clay_switch, and a Python LOP rewrites
displayColor per mode. Everything else (lights, cameras, Karma settings) is the scene's own.
"""
import os, sys, json
HIP = os.path.dirname(os.path.abspath(__file__))
MODE, CAM, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
LOOK = sys.argv[4] if len(sys.argv) > 4 else 'sunny'
sys.path.insert(0, os.path.expanduser('~/HoudiniProjects/houdini-mcp'))
import hou

hou.hipFile.load(os.path.join(HIP, 'SanFranciscoHouse_v4_hda.hipnc'), suppress_save_prompt=True, ignore_load_warnings=True)
st = hou.node('/stage')
src = hou.node('/stage/sfh_clay_switch')
outs = [(o, i) for o in src.outputs() for i, inp in enumerate(o.inputs()) if inp == src]

lib = st.createNode('materiallibrary', 'viz_lib'); lib.setInput(0, src)
lib.parm('matpathprefix').set('/viz/')
surf = lib.createNode('mtlxstandard_surface', 'viz')
cd = lib.createNode('mtlxgeompropvalue', 'cd')
cd.parm('signature').set('color3'); cd.parm('geomprop').set('displayColor')
surf.setInput(surf.inputIndex('base_color'), cd, 0)
surf.parm('specular').set(0.15); surf.parm('specular_roughness').set(0.55)
asg = st.createNode('assignmaterial', 'viz_assign'); asg.setInput(0, lib)
asg.parm('primpattern1').set('/World/** ^/World/environment/** ^/World/street/street_furniture/lamp_post_*/**')
asg.parm('matspecpath1').set('/viz/viz')

CODE = r'''
import colorsys, zlib
from pxr import Usd, UsdGeom, Sdf, Vt, Gf
MODE = %r
stage = hou.pwd().editableStage()
bd = stage.GetPrimAtPath('/World/backdrop')
if bd: bd.SetActive(False)      # the far-side backdrop is not the subject (and sits in front of high cameras)
def lin(rgb): return Gf.Vec3f(*[c ** 2.2 for c in rgb])
def col(key, s=0.55, v=0.9):
    return lin(colorsys.hsv_to_rgb((zlib.crc32(key.encode()) %% 997) / 997.0, s, v))
GREY, PINK, FOLIAGE = lin((0.86, 0.86, 0.84)), lin((0.94, 0.25, 0.55)), lin((0.35, 0.62, 0.45))
def proto_col(k): return lin(colorsys.hsv_to_rgb((k %% 8) / 8.0, 0.75, 0.95))
def setpv(prim, values, interp):
    pv = UsdGeom.PrimvarsAPI(prim).CreatePrimvar('displayColor', Sdf.ValueTypeNames.Color3fArray, interp)
    pv.Set(Vt.Vec3fArray(values)); pv.BlockIndices()
for p in stage.Traverse():
    path = str(p.GetPath())
    if not path.startswith('/World') or path.startswith('/World/environment'): continue
    if p.IsA(UsdGeom.Mesh):
        n = len(UsdGeom.Mesh(p).GetFaceVertexCountsAttr().Get() or [])
        if n == 0: continue
        lamp = 'street_furniture/Prototypes' in path
        blob = 'foliage/Prototypes/blob_' in path
        if MODE == 'material':
            arr = [GREY] * n
            for s in UsdGeom.Subset.GetAllGeomSubsets(UsdGeom.Imageable(p)):
                c = col(s.GetPrim().GetName(), 0.6, 0.92)
                for i in s.GetIndicesAttr().Get(): arr[i] = c
        elif MODE == 'object':
            if lamp: c = PINK
            elif blob: c = FOLIAGE                                    # all foliage = one PointInstancer prim
            elif path.startswith('/World/street'): c = col(path.rsplit('/', 1)[0], 0.22, 0.9)   # by class: muted
            else: c = col(path.rsplit('/', 1)[0])                     # house objects: one colour per prim
            arr = [c] * n
        else:
            arr = [PINK if lamp else (proto_col(int(path.split('blob_')[1].split('/')[0])) if blob else GREY)] * n
        setpv(p, arr, UsdGeom.Tokens.uniform)
    elif p.IsA(UsdGeom.PointInstancer):
        pi = UsdGeom.PointInstancer(p)
        idx = pi.GetProtoIndicesAttr().Get() or []
        if MODE == 'material': vals = [col('material_leaf', 0.6, 0.92)] * len(idx)
        elif MODE == 'object': vals = [FOLIAGE] * len(idx)
        else: vals = [proto_col(int(k)) for k in idx]
        setpv(p, vals, UsdGeom.Tokens.vertex)
''' % MODE
py = st.createNode('pythonscript', 'viz_colors'); py.setInput(0, asg); py.parm('python').set(CODE)
for o, i in outs:
    o.setInput(i, py)

from houdini_mcp import houdini_listener as L
L.OVERRIDES.update({'auto_save': False, 'headless_allow_save': False, 'allow_reload': False})
L.load_config()
r = L.cmd_quick_render('/cameras/' + CAM, width=int(os.environ.get('VIZ_WIDTH', 1280)), samples=int(os.environ.get('VIZ_SAMPLES', 32)), look=LOOK)
import shutil
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
shutil.copy(r['exr'], OUT)
print(json.dumps({'mode': MODE, 'camera': CAM, 'out': OUT, 'seconds': r['seconds']}))
