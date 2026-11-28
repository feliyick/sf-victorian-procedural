"""
usd_publish.py - write the street as a production-style USD package (run in hython; never saves the .hip):

    hython usd_publish.py [--hip SanFranciscoHouse_v4_hda.hipnc] [--out usd_publish/street]

Layout written to --out:
    street_scene.usd          root layer: /World (assembly) with one PAYLOAD per house and per street part,
                              sublayers looks.usd. Open it unloaded to browse the street for almost nothing.
    houses/house_<n>.usd      one asset per house: geometry + semantic labels only (root prim /house_<n>,
                              kind component). Opens on its own, e.g. for a MuJoCo or Isaac scene of one house.
    street.usd                road, sidewalk, street furniture, vegetation; foliage is ONE PointInstancer
    backdrop.usd, environment.usd
    looks.usd                 material bindings as overs on the geometry + the MaterialX file as a sublayer
                              (look kept apart from geometry, so assets stay valid USD when opened alone)
    metrics.json              file sizes, prim counts, load times unloaded / loaded

Reads the live Solaris network: geometry + labels from /stage/sfh_semantics, bindings from /stage/sfh_assign,
the .mtlx path from /stage/sfh_mtlx. Everything comes from the scene as built (usd_structure -> SOP Import ->
sfh_semantics), so re-running after a seed change publishes the new street.
"""
import argparse, json, os, resource, sys, time

ap = argparse.ArgumentParser()
ap.add_argument('--hip', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SanFranciscoHouse_v4_hda.hipnc'))
ap.add_argument('--out', default=None, help='output folder (default $HIP/usd_publish/street)')
ap.add_argument('--geo-lop', default='/stage/sfh_semantics')
ap.add_argument('--look-lop', default='/stage/sfh_assign')
ap.add_argument('--mtlx-lop', default='/stage/sfh_mtlx')
a = ap.parse_args()

import hou
from pxr import Usd, UsdGeom, UsdShade, Sdf, Kind

t0 = time.time()
hou.hipFile.load(a.hip, suppress_save_prompt=True, ignore_load_warnings=True)
HIP = os.path.dirname(os.path.abspath(a.hip))
OUT = os.path.abspath(a.out or os.path.join(HIP, 'usd_publish', 'street'))
os.makedirs(os.path.join(OUT, 'houses'), exist_ok=True)
print('loaded %s (%.1fs)' % (a.hip, time.time() - t0), flush=True)


def new_layer(path):
    if os.path.exists(path):
        os.remove(path)                                  # Sdf.Layer.CreateNew refuses existing files
    lay = Sdf.Layer.CreateNew(path)
    lay.SetPermissionToEdit(True)
    lay.pseudoRoot.SetInfo('metersPerUnit', 1.0)         # Houdini units are metres, Y up
    lay.pseudoRoot.SetInfo('upAxis', 'Y')
    return lay


# ---------------------------------------------------------------- geometry assets (one per house / street part)
t = time.time()
geo = hou.node(a.geo_lop).stage()
flat = geo.Flatten()                                     # composed geometry + labels as one in-memory layer
print('flattened %s (%.1fs)' % (a.geo_lop, time.time() - t), flush=True)

assets = []                                              # (scene path, file relative to OUT, root prim name, kind)
houses = sorted((p.GetName() for p in geo.GetPrimAtPath('/World/houses').GetChildren()),
                key=lambda n: int(n.split('_')[-1]))
for h in houses:
    assets.append(('/World/houses/' + h, 'houses/%s.usd' % h, h, Kind.Tokens.component))
for part in ('street', 'backdrop', 'environment'):
    if geo.GetPrimAtPath('/World/' + part):
        assets.append(('/World/' + part, '%s.usd' % part, part, None))

for src, rel, name, _ in assets:
    lay = new_layer(os.path.join(OUT, rel))
    # SdfCopySpec also remaps relationship targets inside the copied tree (the PointInstancer's prototypes)
    Sdf.CopySpec(flat, Sdf.Path(src), lay, Sdf.Path('/' + name))
    # native instances (lamp posts): Flatten() points each instanceable prim at a root /Flattened_Prototype_N.
    # Copy those into this file too, as 'class' prims: internal references resolve inside the asset file, but a
    # class prim is never drawn by itself and isn't part of the defaultPrim the payload brings into the street.
    protos = set()
    def find_refs(path):
        spec = lay.GetPrimAtPath(path)
        if spec and spec.hasReferences:
            for r in spec.referenceList.GetAddedOrExplicitItems():
                if not r.assetPath and str(r.primPath).startswith('/Flattened_Prototype'):
                    protos.add(r.primPath)
    lay.Traverse(Sdf.Path('/' + name), find_refs)
    for pp in sorted(protos):
        Sdf.CopySpec(flat, pp, lay, pp)
        lay.GetPrimAtPath(pp).specifier = Sdf.SpecifierClass
    lay.defaultPrim = name
    lay.Save()
print('wrote %d geometry assets' % len(assets), flush=True)

# ---------------------------------------------------------------- looks.usd: bindings as overs + MaterialX sublayer
look = hou.node(a.look_lop).stage()
mtlx_node = hou.node(a.mtlx_lop)
mtlx = None
for p in mtlx_node.parms():
    if p.name().startswith('filepath') and str(p.eval()).endswith('.mtlx'):
        mtlx = p.eval()
lay = new_layer(os.path.join(OUT, 'looks.usd'))
if mtlx:
    lay.subLayerPaths.append(os.path.relpath(os.path.join(HIP, mtlx) if not os.path.isabs(mtlx) else mtlx, OUT))
nbind = 0
for prim in Usd.PrimRange(look.GetPrimAtPath('/World')):
    rel = prim.GetRelationship('material:binding')
    if not rel or not rel.GetTargets():
        continue
    spec = Sdf.CreatePrimInLayer(lay, prim.GetPath())
    spec.specifier = Sdf.SpecifierOver
    schemas = Sdf.TokenListOp(); schemas.prependedItems = ['MaterialBindingAPI']
    spec.SetInfo('apiSchemas', schemas)
    r = Sdf.RelationshipSpec(spec, 'material:binding', custom=False)
    r.targetPathList.explicitItems = rel.GetTargets()
    nbind += 1
lay.Save()
print('looks.usd: %d bindings, MaterialX %s' % (nbind, mtlx), flush=True)

# ---------------------------------------------------------------- street_scene.usd: the assembly, all payloads
root_path = os.path.join(OUT, 'street_scene.usd')
lay = new_layer(root_path)
lay.subLayerPaths.append('looks.usd')
stage = Usd.Stage.Open(lay)
world = UsdGeom.Xform.Define(stage, '/World')
Usd.ModelAPI(world).SetKind(Kind.Tokens.assembly)
stage.SetDefaultPrim(world.GetPrim())
grp = UsdGeom.Xform.Define(stage, '/World/houses')
Usd.ModelAPI(grp).SetKind(Kind.Tokens.group)
for src, rel, name, kind in assets:
    prim = UsdGeom.Xform.Define(stage, src).GetPrim()
    prim.GetPayloads().AddPayload('./' + rel)           # the asset's defaultPrim lands here
    if kind:
        Usd.ModelAPI(prim).SetKind(kind)                 # known even while unloaded (model hierarchy browsing)
lay.Save()
print('wrote %s' % root_path, flush=True)


# ---------------------------------------------------------------- metrics

def count(stage):
    n = {'prims': 0, 'meshes': 0, 'faces': 0, 'point_instancers': 0, 'instances': 0, 'native_instances': 0,
         'prototypes': len(stage.GetPrototypes()), 'labelled': 0}
    for p in stage.Traverse():
        n['prims'] += 1
        if p.IsInstance():
            n['native_instances'] += 1
        if p.IsA(UsdGeom.Mesh):
            n['meshes'] += 1
            c = UsdGeom.Mesh(p).GetFaceVertexCountsAttr().Get()
            n['faces'] += len(c) if c is not None else 0
        elif p.IsA(UsdGeom.PointInstancer):
            n['point_instancers'] += 1
            pi = UsdGeom.PointInstancer(p).GetProtoIndicesAttr().Get()
            n['instances'] += len(pi) if pi is not None else 0
        if p.HasAttribute('semantics:labels:class'):
            n['labelled'] += 1
    return n


def size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


m = {'out': OUT}
Usd.Stage.Open(root_path, Usd.Stage.LoadNone)            # warm the file cache so both timings are fair
t = time.time(); s0 = Usd.Stage.Open(root_path, Usd.Stage.LoadNone); m['open_unloaded_s'] = round(time.time() - t, 3)
m['unloaded'] = count(s0)
t = time.time(); s1 = Usd.Stage.Open(root_path, Usd.Stage.LoadAll); m['open_loaded_s'] = round(time.time() - t, 3)
m['loaded'] = count(s1)
one = os.path.join(OUT, 'houses', houses[0] + '.usd')
t = time.time(); s2 = Usd.Stage.Open(one); m['open_one_house_s'] = round(time.time() - t, 3)
m['one_house'] = dict(count(s2), file=os.path.relpath(one, OUT))
# a single house loaded into the full street: load just that payload
s3 = Usd.Stage.Open(root_path, Usd.Stage.LoadNone); s3.Load('/World/houses/' + houses[0])
m['street_with_one_house_loaded'] = count(s3)
files = {os.path.relpath(os.path.join(d, f), OUT): size(os.path.join(d, f))
         for d, _, fs in os.walk(OUT) for f in fs if f.endswith('.usd')}
m['files_bytes'] = files
m['total_bytes'] = sum(files.values())
if mtlx:
    m['materialx_file_bytes'] = size(os.path.join(HIP, mtlx) if not os.path.isabs(mtlx) else mtlx)
json.dump(m, open(os.path.join(OUT, 'metrics.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in m.items() if k != 'files_bytes'}, indent=1))
print('done in %.1fs' % (time.time() - t0))
