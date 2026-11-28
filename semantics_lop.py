# sfh_semantics (Python LOP, right after sfh_house_import): turns the per-object hierarchy that usd_structure
# builds into a labelled USD scene that USD-native data tools (Omniverse Replicator / Isaac Sim) can read.
#   * semantic class label on every object prim, in both forms Isaac reads:
#       UsdSemantics  (Isaac Sim 4.5+):  apiSchemas SemanticsLabelsAPI:class,  token[] semantics:labels:class
#       legacy Semantics schema:         apiSchemas SemanticsAPI:Semantics,    semantic:Semantics:params:semanticType/Data
#     Labels are inherited down the tree, so a label on house_3 covers every part of house_3 that has none.
#   * sfh:instance_id / sfh:house_id on object prims (the same ids as the COCO annotations and the label AOV)
#   * model kinds: /World assembly, groups, each house a component, its parts subcomponents
#   * material subsets: SOP Import writes familyName "material"; UsdShade only binds subsets in the
#     "materialBind" family, so they are renamed here (and the family is marked a partition).
# Runs on every cook: no undo steps, the node comment only changes inside hou.undos.disabler().
import re
import hou
from pxr import Usd, UsdGeom, Sdf, Kind

node = hou.pwd()
stage = node.editableStage()


def note(text):
    if node.comment() != text:
        with hou.undos.disabler():
            node.setComment(text)


def label(prim, cls):
    prim.AddAppliedSchema('SemanticsLabelsAPI:class')
    prim.CreateAttribute('semantics:labels:class', Sdf.ValueTypeNames.TokenArray).Set([cls])
    prim.AddAppliedSchema('SemanticsAPI:Semantics')
    prim.CreateAttribute('semantic:Semantics:params:semanticType', Sdf.ValueTypeNames.String).Set('class')
    prim.CreateAttribute('semantic:Semantics:params:semanticData', Sdf.ValueTypeNames.String).Set(cls)


def kind(prim, k):
    Usd.ModelAPI(prim).SetKind(k)


OBJ = re.compile(r'^([a-z_]+?)(?:_(\d{3}))?$')        # door_300 -> ('door', '300'), ornament -> ('ornament', None)
world = stage.GetPrimAtPath('/World')
counts = {'objects': 0, 'houses': 0, 'subsets': 0}
if world and world.IsValid():
    kind(world, Kind.Tokens.assembly)
    for prim in Usd.PrimRange(world):
        path = prim.GetPath()
        depth = path.pathElementCount
        typ = prim.GetTypeName()
        if typ == 'GeomSubset':
            fam = prim.GetAttribute('familyName')
            if fam and fam.Get() == 'material':
                fam.Set('materialBind')
                UsdGeom.Subset.SetFamilyType(UsdGeom.Imageable(prim.GetParent()), 'materialBind',
                                             UsdGeom.Tokens.partition)
                counts['subsets'] += 1
            continue
        if typ != 'Xform':
            continue
        top = path.GetPrefixes()[1].name if depth >= 2 else ''
        name = prim.GetName()
        if depth == 2:                                   # /World/houses, /World/street, /World/backdrop ...
            kind(prim, Kind.Tokens.group if top in ('houses', 'street') else Kind.Tokens.component)
            if top == 'backdrop':
                label(prim, 'distant_building')
            continue
        if top == 'houses':
            hm = re.match(r'house_(\d+)$', path.GetPrefixes()[2].name)
            if not hm:
                continue
            h = int(hm.group(1))
            if depth == 3:                               # the house
                kind(prim, Kind.Tokens.component)
                label(prim, 'house')
                prim.CreateAttribute('sfh:house_id', Sdf.ValueTypeNames.Int).Set(h)
                counts['houses'] += 1
                continue
            m = OBJ.match(name)
            if not m:
                continue
            cls, local = m.group(1), m.group(2)
            kind(prim, Kind.Tokens.subcomponent)
            label(prim, cls)
            prim.CreateAttribute('sfh:house_id', Sdf.ValueTypeNames.Int).Set(h)
            if local:
                prim.CreateAttribute('sfh:instance_id', Sdf.ValueTypeNames.Int).Set((h + 1) * 1000 + int(local))
            counts['objects'] += 1
        elif top == 'street':
            if depth == 3:                               # /World/street/<class>
                kind(prim, Kind.Tokens.component)
                label(prim, name)
            elif depth == 4:
                kind(prim, Kind.Tokens.subcomponent)
                counts['objects'] += 1
note('%(houses)d houses, %(objects)d labelled objects, %(subsets)d material subsets' % counts)
