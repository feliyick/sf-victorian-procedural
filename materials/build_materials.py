# Generates house_materials.mtlx (MaterialX 1.38, procedural, no textures / no UVs)
import itertools
lines = []
uid = itertools.count()

class N:
    def __init__(s, name, typ, out=None): s.name, s.typ, s.out = name, typ, out
    def o(s, out): return N(s.name, s.typ_of(out), out)
    def typ_of(s, out): return 'float'

def lit(t, v):
    if isinstance(v, (tuple, list)): return t, ', '.join(repr(float(x)) for x in v)
    return t, repr(float(v)) if t == 'float' else str(v)

def node(cat, typ, prefix, **inputs):
    name = '%s_%d' % (prefix, next(uid))
    body = []
    for k, v in inputs.items():
        if isinstance(v, N):
            attr = ' output="%s"' % v.out if v.out else ''
            body.append('    <input name="%s" type="%s" nodename="%s"%s />' % (k, v.typ, v.name, attr))
        else:
            t, val = v
            body.append('    <input name="%s" type="%s" value="%s" />' % (k, t, val))
    lines.append('  <%s name="%s" type="%s">' % (cat, name, typ))
    lines.extend(body)
    lines.append('  </%s>' % cat)
    return N(name, typ)

F = lambda v: ('float', repr(float(v)))
C = lambda *v: ('color3', ', '.join(repr(float(x)) for x in v))
V = lambda *v: ('vector3', ', '.join(repr(float(x)) for x in v))
def f(x): return x if isinstance(x, N) else F(x)

# ---- float math helpers ----
def add(a, b, t='float'):  return node('add', t, 'add', in1=a if isinstance(a, N) else F(a), in2=b if isinstance(b, N) else F(b))
def sub(a, b, t='float'):  return node('subtract', t, 'sub', in1=f(a), in2=f(b))
def mul(a, b, t='float'):  return node('multiply', t, 'mul', in1=f(a), in2=f(b))
def div(a, b):             return node('divide', 'float', 'div', in1=f(a), in2=f(b))
def floor(a):              return node('floor', 'float', 'floor', **{'in': a})
def fract(a):              return sub(a, floor(a))
def smooth(a, lo, hi):     return node('smoothstep', 'float', 'smooth', **{'in': a, 'low': f(lo), 'high': f(hi)})
def clamp01(a):            return node('clamp', 'float', 'clamp', **{'in': a, 'low': F(0), 'high': F(1)})
def mixf(fg, bg, m):       return node('mix', 'float', 'mix', fg=f(fg), bg=f(bg), mix=m)
def mixc(fg, bg, m):       return node('mix', 'color3', 'mixc', fg=fg if isinstance(fg, N) else C(*fg), bg=bg if isinstance(bg, N) else C(*bg), mix=m)
def cmul(c, s):            return node('multiply', 'color3', 'cmul', in1=c if isinstance(c, N) else C(*c), in2=f(s))
def ifgt(v1, v2, a, b):    return node('ifgreater', 'float', 'ifgt', value1=f(v1), value2=f(v2), in1=f(a), in2=f(b))
def unit(n):               return clamp01(add(mul(n, 0.5), 0.5))      # noise -1..1 -> 0..1

def section(title): lines.append('\n  <!-- ===== %s ===== -->' % title)

# ---------------- shared inputs ----------------
section('shared: world position, noise, palette colour')
P = node('position', 'vector3', 'P', space=('string', 'world'))
x = N(node('separate3', 'multioutput', 'sep', **{'in': P}).name, 'float', 'outx')
sep_name = x.name
y = N(sep_name, 'float', 'outy'); z = N(sep_name, 'float', 'outz')
P_big   = node('multiply', 'vector3', 'Pbig',   in1=P, in2=F(0.6))
P_small = node('multiply', 'vector3', 'Psmall', in1=P, in2=F(4.0))
P_fine  = node('multiply', 'vector3', 'Pfine',  in1=P, in2=F(90.0))
noise_big   = unit(node('fractal3d', 'float', 'fracbig',   position=P_big,   octaves=('integer', 4), amplitude=F(1)))
noise_small = unit(node('fractal3d', 'float', 'fracsmall', position=P_small, octaves=('integer', 4), amplitude=F(1)))
cd = node('geompropvalue', 'color3', 'paintcolour', geomprop=('string', 'displayColor'), default=C(0.5, 0.5, 0.5))
near_ground = sub(1.0, smooth(y, 0.0, 1.2))                     # 1 at the street, 0 above 1.2 m

materials = []
def material(name, **ss):
    shader = node('standard_surface', 'surfaceshader', name + '_shader', **ss)
    lines.append('  <surfacematerial name="%s" type="material">' % name)
    lines.append('    <input name="surfaceshader" type="surfaceshader" nodename="%s" />' % shader.name)
    lines.append('  </surfacematerial>')
    materials.append(name)

# ---------------- body: clapboard siding (+ optional brick base) ----------------
section('siding: painted clapboards, grime near the street, optional brick base')
board = fract(div(y, 0.15))                                     # 0..1 up each 15 cm board
lap_shadow = smooth(board, 0.0, 0.12)                           # dark line under each board's lap
shade = mul(mixf(1.0, 0.62, lap_shadow), add(mul(board, 0.06), 0.94))
siding = cmul(cd, shade)
grime = mul(near_ground, noise_big)
siding = mixc(cmul(siding, 0.55), siding, mul(grime, 0.6))

u = add(x, z)                                                   # horizontal coordinate on front AND side walls
row = floor(div(y, 0.0762))
bu = add(div(u, 0.2032), mul(node('modulo', 'float', 'mod', in1=row, in2=F(2)), 0.5))
bx = fract(bu); by = sub(div(y, 0.0762), row)
mortar = mul(mul(smooth(bx, 0.0, 0.05), sub(1.0, smooth(bx, 0.95, 1.0))),
             mul(smooth(by, 0.0, 0.09), sub(1.0, smooth(by, 0.91, 1.0))))          # 1 = brick face, 0 = mortar
cell = node('cellnoise3d', 'float', 'brickcell', position=node('combine3', 'vector3', 'brickid', in1=floor(bu), in2=row, in3=F(0)))
brick_face = cmul(mixc((0.56, 0.25, 0.16), (0.32, 0.12, 0.08), cell), add(mul(noise_small, 0.3), 0.85))
brick = mixc(brick_face, (0.62, 0.60, 0.56), mortar)
base_brick = node('geompropvalue', 'float', 'basebrick', geomprop=('string', 'base_brick'), default=F(0))
base_top   = node('geompropvalue', 'float', 'basetop',   geomprop=('string', 'base_top'),   default=F(0))
is_base = mul(base_brick, ifgt(base_top, y, 1.0, 0.0))
material('siding',
         base_color=mixc(brick, siding, is_base),
         specular=F(0.35),
         specular_roughness=mixf(0.85, add(mul(noise_small, 0.15), 0.5), is_base))

# ---------------- trim / sash / door ----------------
section('trim, sash, door: painted wood')
trim_col = mixc(cmul(cd, 0.7), cmul(cd, add(mul(noise_small, 0.04), 0.96)), mul(grime, 0.4))
material('trim', base_color=trim_col, specular=F(0.5), specular_roughness=add(mul(noise_small, 0.1), 0.3))
material('sash', base_color=cd, specular=F(0.5), specular_roughness=F(0.25))
material('door', base_color=cd, specular=F(0.5), specular_roughness=F(0.3), coat=F(1.0), coat_roughness=F(0.08))

# ---------------- glass ----------------
section('glass: clear and thin, so the room / curtains behind it show through, with real reflections')
material('glass', base=F(0.0), specular=F(1.0), specular_IOR=F(1.52), specular_roughness=F(0.0),
         transmission=F(1.0), transmission_color=C(0.93, 0.96, 0.95), thin_walled=('boolean', 'true'))

section('glass_dark: garage + door glass (nothing modelled behind it): dark and reflective')
material('glass_dark', base_color=C(0.008, 0.008, 0.009), base=F(1.0), specular=F(1.0), specular_IOR=F(1.52),
         specular_roughness=F(0.0), coat=F(1.0), coat_IOR=F(1.5))

section('curtains, blinds, rooms, plants (colours come from the window_dressing node)')
material('curtain', base_color=cd, specular=F(0.1), specular_roughness=F(0.8), sheen=F(0.6), sheen_color=C(1, 1, 1),
         thin_walled=('boolean', 'true'))
material('curtain_sheer', base_color=cd, specular=F(0.05), specular_roughness=F(0.9), sheen=F(0.4),
         opacity=C(0.55, 0.55, 0.55), thin_walled=('boolean', 'true'))
lit = node('geompropvalue', 'float', 'roomlit', geomprop=('string', 'lit'), default=F(1.0))
glow_t = node('geompropvalue', 'float', 'glowt', geomprop=('string', 'glow_t'), default=F(0.5))
glow_t = mul(glow_t, glow_t)                                                                # most rooms warm, a few whiter
cd_lum = node('dotproduct', 'float', 'cdlum', in1=node('convert', 'vector3', 'cdvec', **{'in': cd}), in2=V(0.3, 0.55, 0.15))
room_glow = cmul(mixc((1.0, 0.93, 0.82), (1.0, 0.58, 0.26), glow_t), mul(mul(lit, 1.4), clamp01(mul(cd_lum, 14.0))))   # floor / sides / shades glow by their own tone                     # warm incandescent interior, only where lit = 1
material('room', base_color=cd, specular=F(0.05), specular_roughness=F(1.0),
         emission=F(1.0), emission_color=room_glow)     # always on: the sun drowns it by day, it carries the night          # the Dusk look turns emission up: lit rooms
material('plant', base_color=cd, specular=F(0.3), specular_roughness=F(0.5), subsurface=F(0.2),
         subsurface_color=cd, thin_walled=('boolean', 'true'))

# ---------------- garage: painted metal with rust at the bottom ----------------
section('garage door: clean painted metal, only a faint darkening at the street')
dirt_col   = cmul(cd, 0.8)                                                # same paint, slightly darker
dirt       = sub(1.0, smooth(y, 0.0, 0.5))                                # fades out by 50 cm
garage_col = mixc(dirt_col, cd, mul(dirt, 0.3))
material('garage', base_color=garage_col, specular=F(0.6), specular_roughness=F(0.35))

# ---------------- iron: rails, with rust spots ----------------
section('iron: dark painted metal with rust spots')
rust_col = cmul((0.42, 0.28, 0.17), add(mul(noise_big, 0.3), 0.85))                 # desaturated brown-orange
iron_rust = mul(smooth(noise_small, 0.62, 0.8), 0.6)        # small, faded rust spots
material('iron', base_color=mixc(rust_col, (0.035, 0.035, 0.04), iron_rust), metalness=mixf(0.0, 0.6, iron_rust),
         specular_roughness=mixf(0.9, 0.4, iron_rust))

# ---------------- stone ----------------
section('granite steps: speckled grey')
speck = node('cellnoise3d', 'float', 'speck', position=P_fine)
granite = mixc((0.72, 0.71, 0.68), (0.44, 0.43, 0.42), speck)
granite = mixc((0.12, 0.12, 0.12), granite, ifgt(speck, 0.93, 1.0, 0.0))
material('granite', base_color=cmul(granite, add(mul(noise_big, 0.2), 0.9)), specular=F(0.5), specular_roughness=F(0.45))

section('marble steps: white with grey veins (Italianate entries)')
vein_in = add(mul(add(add(x, mul(y, 0.5)), z), 4.0),
              mul(node('fractal3d', 'float', 'veinwarp', position=node('multiply', 'vector3', 'Pvein', in1=P, in2=F(1.5)), octaves=('integer', 5)), 6.0))
vein = sub(1.0, smooth(node('absval', 'float', 'abs', **{'in': node('sin', 'float', 'sin', **{'in': vein_in})}), 0.0, 0.15))
material('marble', base_color=mixc((0.45, 0.45, 0.47), (0.93, 0.92, 0.89), mul(vein, 0.8)), specular=F(0.6), specular_roughness=F(0.15))

# ---------------- roof + ground ----------------
section('shingles: fish-scale shingles in the gable (Queen Anne)')
su  = div(add(x, z), 0.16)
srow = floor(div(y, 0.12))
suo = add(su, mul(node('modulo', 'float', 'mod', in1=srow, in2=F(2)), 0.5))
fu  = sub(fract(suo), 0.5)
fv  = sub(div(y, 0.12), srow)                                                # 0 at the bottom of each row
dv  = sub(fv, 0.5)
d2  = add(mul(fu, fu), mul(dv, dv))                                           # squared distance from the round bottom's centre
edge = mul(smooth(d2, 0.16, 0.25), ifgt(0.5, fv, 1.0, 0.0))                   # dark outline round the bottom of each scale
scell = node('cellnoise3d', 'float', 'shinglecell', position=node('combine3', 'vector3', 'shingleid', in1=floor(suo), in2=srow, in3=F(3)))
shade = mul(sub(1.0, mul(edge, 0.5)), add(mul(scell, 0.12), 0.9))
material('shingle', base_color=cmul(cd, shade), specular=F(0.35), specular_roughness=F(0.6))

section('roof: weathered tar')
Nw = node('normal', 'vector3', 'Nworld', space=('string', 'world'))
ny = N(node('separate3', 'multioutput', 'sepN', **{'in': Nw}).name, 'float', 'outy')
slope_m = sub(1.0, smooth(node('absval', 'float', 'absny', **{'in': ny}), 0.9, 0.98))     # 1 on pitched roofs, 0 on flat
rrow = floor(div(y, 0.18)); rfv = sub(div(y, 0.18), rrow)
course = smooth(rfv, 0.0, 0.1)                                                            # dark line under each course
ru = add(div(add(x, z), 0.32), mul(node('modulo', 'float', 'mod', in1=rrow, in2=F(2)), 0.5))
rfu = fract(ru)
tab = mul(smooth(rfu, 0.0, 0.05), sub(1.0, smooth(rfu, 0.95, 1.0)))
rcell = node('cellnoise3d', 'float', 'roofcell', position=node('combine3', 'vector3', 'roofid', in1=floor(ru), in2=rrow, in3=F(7)))
rshade = mul(mul(mixf(1.0, 0.6, course), mixf(1.0, 0.75, tab)), add(mul(rcell, 0.25), 0.85))
rshade = mixf(rshade, 1.0, slope_m)                                                       # flat roofs: no courses
material('roof', base_color=cmul(cmul(cd, rshade), add(mul(noise_big, 0.3), 0.85)), specular=F(0.25), specular_roughness=F(0.85))

section('sidewalk: concrete slabs with joints and stains')
jx = fract(div(x, 1.5)); jz = fract(div(z, 1.5))
joints = mul(mul(smooth(jx, 0.0, 0.008), sub(1.0, smooth(jx, 0.992, 1.0))),
             mul(smooth(jz, 0.0, 0.008), sub(1.0, smooth(jz, 0.992, 1.0))))
concrete = cmul((0.56, 0.55, 0.53), mul(mixf(1.0, 0.55, joints), add(mul(noise_big, 0.3), 0.85)))
material('concrete', base_color=concrete, specular=F(0.3), specular_roughness=F(0.8))

# ---------------- street (v6): colours come from the street_build node's Cd ----------------
section('asphalt: aggregate speckle over the patch colour, darker oily centre of each lane')
agg = node('cellnoise3d', 'float', 'aggregate', position=P_fine)
asphalt_shade = mul(add(mul(agg, 0.35), 0.8), add(mul(noise_big, 0.3), 0.85))
material('asphalt', base_color=cmul(cd, asphalt_shade), specular=F(0.25),
         specular_roughness=add(mul(noise_small, 0.15), 0.75))

section('sidewalk: concrete slabs, each slab tinted by Cd, stains from noise')
material('sidewalk', base_color=cmul(cd, mul(add(mul(noise_big, 0.3), 0.82), add(mul(agg, 0.08), 0.96))),
         specular=F(0.3), specular_roughness=F(0.85))

section('soil / bark / leaves / painted metal / road paint')
material('soil', base_color=cmul(cd, add(mul(noise_small, 0.4), 0.75)), specular=F(0.1), specular_roughness=F(1.0))
bark_n = unit(node('fractal3d', 'float', 'barkn', position=node('multiply', 'vector3', 'Pbark', in1=P, in2=V(14.0, 1.5, 14.0)), octaves=('integer', 3), amplitude=F(1)))
material('bark', base_color=cmul(cd, add(mul(bark_n, 0.5), 0.6)), specular=F(0.15), specular_roughness=F(0.9))
material('leaf', base_color=cmul(cd, add(mul(noise_small, 0.35), 0.8)), specular=F(0.25), specular_roughness=F(0.55),
         subsurface=F(0.25), subsurface_color=cd, thin_walled=('boolean', 'true'))
material('metal', base_color=cd, specular=F(0.6), specular_roughness=add(mul(noise_small, 0.15), 0.3))
material('street_paint', base_color=cmul(cd, add(mul(agg, 0.25), 0.8)), specular=F(0.3), specular_roughness=F(0.7))

section('lamp: street lamp + porch light glass (the Dusk look turns emission up)')
lamp_on = node('geompropvalue', 'float', 'lampon', geomprop=('string', 'lamp_on'), default=F(0.0))
material('lamp', base_color=C(0.55, 0.53, 0.48), specular=F(0.5), specular_roughness=F(0.2),
         emission=mul(lamp_on, 12.0), emission_color=C(1.0, 0.78, 0.45))      # on only for dusk / night (street_build writes lamp_on)

section('clouds: a lit, cut-out cloud layer on a high dome (km-scale noise), shaded by the real sun + sky')
P_cloud = node('multiply', 'vector3', 'Pcloud', in1=P, in2=V(0.0007, 0.004, 0.0028))       # stretched: soft streaky high cloud
cloud_n = unit(node('fractal3d', 'float', 'cloudn', position=P_cloud, octaves=('integer', 5), amplitude=F(1)))
cloud_m = mul(smooth(cloud_n, 0.6, 0.85), 0.8)                                                # sparser, never fully opaque
material('clouds', base_color=C(1.0, 0.98, 0.96), base=F(0.8), specular=F(0.0),
         emission=F(0.35), emission_color=C(1.0, 0.97, 0.94),                                  # self-lit a little: no grey smudges
         opacity=mixc((1.0, 1.0, 1.0), (0.0, 0.0, 0.0), cloud_m), thin_walled=('boolean', 'true'))

section('sky: an emissive backdrop, colour from displayColor (the night sky dome geometry)')
skycol = node('geompropvalue', 'color3', 'skycol', geomprop=('string', 'skycol'), default=C(0.02, 0.03, 0.08))
material('sky', base=F(0.0), specular=F(0.0), emission=F(1.0), emission_color=skycol)   # per-POINT colour: smooth gradient, no bands

xml = ['<?xml version="1.0"?>',
       '<!-- house_materials.mtlx : procedural facade materials (no textures, no UVs).',
       '     Every pattern is built from WORLD position, so it works on any generated house.',
       '     Paint colours come from the displayColor primvar written by the paint SOP. -->',
       '<materialx version="1.38">'] + lines + ['</materialx>']
import sys
out_name = sys.argv[1] if len(sys.argv) > 1 else 'house_materials.mtlx'
open(out_name, 'w').write('\n'.join(xml) + '\n')
print('materials:', materials, ' nodes:', next(uid))
