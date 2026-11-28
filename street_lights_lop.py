# sfh_street_lights (Python LOP): a real warm light under every street-lamp head, pointing down,
# switched on for dusk (3) and night (5). Positions come from street_build's v[]@lamp_pos.
import hou
from pxr import UsdLux, UsdGeom, Gf
node = hou.pwd(); stage = node.editableStage()
def note(text):
    # node comment = status readout. Only when it changes, and off the undo stack: a cook must never
    # add undo steps or mark the scene unsaved on its own.
    if node.comment() != text:
        with hou.undos.disabler(): node.setComment(text)
# the night sky dome: seen by the camera only, so it doesn't block the light that falls on the street
from pxr import Sdf
sky = stage.GetPrimAtPath('/World/environment/sky/geo')     # usd_structure puts the sky here (was /street/sky)
if sky and sky.IsValid():
    pv = sky.CreateAttribute('primvars:karma:object:rendervisibility', Sdf.ValueTypeNames.String)
    pv.Set('primary')            # camera rays only (Karma token: 'primary')
look = node.evalParm('look')
if look in (3, 5):
    sb = hou.node('/obj/sf_house_geometry/street_build')
    raw = sb.geometry().attribValue('lamp_pos')
    flat = [c for v in raw for c in (v if hasattr(v, '__len__') else (v,))]
    I = node.evalParm('intensity_night' if look == 5 else 'intensity_dusk')
    for i in range(0, len(flat) - 2, 3):
        path = '/lights/street_lamps/lamp_%03d' % (i // 3)
        l = UsdLux.SphereLight.Define(stage, path)
        l.CreateRadiusAttr(0.15); l.CreateIntensityAttr(float(I)); l.CreateColorAttr(Gf.Vec3f(1.0, 0.72, 0.42))
        x = UsdGeom.XformCommonAPI(l.GetPrim())
        x.SetTranslate(Gf.Vec3d(flat[i], flat[i + 1], flat[i + 2])); x.SetRotate(Gf.Vec3f(-90, 0, 0))   # face down
        sh = UsdLux.ShapingAPI.Apply(l.GetPrim())
        sh.CreateShapingConeAngleAttr(65.0); sh.CreateShapingConeSoftnessAttr(0.6)
    note('%d street lights at %g' % (len(flat) // 3, I))
else:
    note('off (daytime look)')
