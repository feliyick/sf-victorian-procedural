# capture_portfolio.py — renders + captures everything for the portfolio, unattended.
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/capture_portfolio.py', encoding='utf-8').read())
#
# Houdini is busy while it runs (Karma renders take minutes each), so start it and walk away.
# Edit the SETTINGS block first. Output: $HIP/render/portfolio/<run>/ ... plus log.txt.
#   beauty/<look>/<camera>.exr       Karma, denoised      (the hero shots)
#   clay/<camera>.exr                Karma, white clay material, same lighting  (form / "AO" look)
#   gl/<camera>.png                  viewport, smooth shaded   (pairs with beauty for unrendered -> rendered swipes)
#   wire/<camera>.png                viewport, wireframe on shaded
#   sweeps/<name>/NN.png             viewport frames while one parameter changes (seed, palette, style, roof...)
#   buildup/NN_<step>.png            one house -> tweaks -> the row -> the street, as a sequence
# Everything you change on the asset / street is put back at the end.
import hou, os, time, traceback

# ======================= SETTINGS =======================
CAMERAS   = 'all'            # 'all' = every /cameras/cam_* prim, or a list like ['cam_wide', 'cam_tele']
LOOKS     = {'sunny': 4, 'golden': 0, 'dusk': 3, 'night': 5}     # sfh_look inputs
# the FINAL SHOT LIST (beauty). Set to None to render every camera in every look instead.
SHOTS = [('night', 'cam_front'), ('night', 'cam_row_up'), ('night', 'cam_wide'),
         ('golden', 'cam_front'), ('golden', 'cam_wide'), ('golden', 'cam_aerial'), ('golden', 'cam_row_down'),
         ('sunny', 'cam_front'), ('sunny', 'cam_street'), ('sunny', 'cam_tele')]
try: SHOTS = SHOTS_OVERRIDE          # a patch can pass its own short list
except NameError: pass
QUICK     = False            # True: 32 samples, fast check of everything.  False: final quality (256 samples)
DO_BEAUTY = True
DO_CLAY   = False
DO_GL     = False
DO_WIRE   = False
DO_SWEEPS = False
DO_BUILD  = False
DO_GALLERY = False            # solo-house gallery: the hero alone (Row Count 1) for many seeds, framed like a real-estate photo
GALLERY_SEEDS = [3, 11, 27, 42, 58, 77, 101, 133, 150, 188, 215, 240, 271, 305, 333, 360]
GALLERY_GL = False           # viewport capture of each gallery house (off: the viewport ignores the lens settings)
GALLERY_KARMA = True         # False = viewport captures only (fast: for picking favourite seeds)
GALLERY_RES = (720, 960)     # square, so tall houses fit without standing in the far-side houses
SWEEP_CAM = 'cam_sweep'      # auto camera re-aimed every frame from the middle of the road (the street changes width as houses change)
RES       = (1280, 720)      # Apprentice maximum
SHOT_RES  = {'cam_front': (1280, 540)}   # per-camera resolution (panoramic strip for the face-on row)
# ========================================================

HIP = hou.text.expandString('$HIP')
RUN = os.path.join(HIP, 'render', 'portfolio', time.strftime('%Y%m%d_%H%M'))
os.makedirs(RUN, exist_ok=True)
LOG = open(os.path.join(RUN, 'log.txt'), 'w')
def log(msg):
    line = '%s  %s' % (time.strftime('%H:%M:%S'), msg); print(line); LOG.write(line + '\n'); LOG.flush()

stage = hou.node('/stage'); NET = hou.node('/obj/sf_house_geometry')
hero = NET.node('victorian_house'); ctl = NET.node('STREET_CONTROLS')
karma = stage.node('sfh_karma_render'); look = stage.node('sfh_look'); lights = stage.node('sfh_lights')
hou.setFrame(1)

# ---------- remember everything we touch ----------
saved = {}
def remember(parm):
    if parm is None or parm.path() in saved: return
    try: saved[parm.path()] = ('expr', parm.expression(), parm.expressionLanguage())
    except hou.OperationFailed: saved[parm.path()] = ('val', parm.eval(), None)
def setp(node, name, value):
    p = node.parm(name)
    if p is None: log('  (no parm %s/%s)' % (node.name(), name)); return
    remember(p); p.deleteAllKeyframes(); p.set(value)
def restore():
    for path, (kind, v, lang) in saved.items():
        p = hou.parm(path)
        if p is None: continue
        p.deleteAllKeyframes()
        if kind == 'expr': p.setExpression(v, lang)
        else: p.set(v)

# ---------- cameras ----------
if CAMERAS == 'all':
    CAMERAS = sorted(p.GetName() for p in stage.node('sfh_shot_cam').stage().Traverse()
                     if p.GetTypeName() == 'Camera' and p.GetName().startswith('cam_')
                     and p.GetName() not in ('cam_sweep', 'cam_gallery'))
log('cameras: %s' % ', '.join(CAMERAS))

# ---------- clay switch (built once, left in the scene, off by default) ----------
def ensure_clay():
    sw = stage.node('sfh_clay_switch')
    if sw: return sw
    lib = stage.createNode('materiallibrary', 'sfh_clay_lib'); lib.setInput(0, lights)
    lib.parm('matpathprefix').set('/clay/') if lib.parm('matpathprefix') else None
    m = lib.createNode('mtlxstandard_surface', 'clay')
    m.parm('base_colorr').set(0.8); m.parm('base_colorg').set(0.8); m.parm('base_colorb').set(0.78)
    m.parm('specular').set(0.1); m.parm('specular_roughness').set(0.7)
    asg = stage.createNode('assignmaterial', 'sfh_clay_assign'); asg.setInput(0, lib)
    asg.parm('primpattern1').set('/house/** /street/**')
    asg.parm('matspecpath1').set('/clay/clay' if lib.parm('matpathprefix') else '/materials/clay')
    sw = stage.createNode('switch', 'sfh_clay_switch')
    nxt = [o for o in lights.outputs() if o != lib]
    sw.setInput(0, lights); sw.setInput(1, asg)
    for o in nxt:
        for i, inp in enumerate(o.inputs()):
            if inp == lights: o.setInput(i, sw)
    sw.parm('input').set(0)
    for i, n in enumerate((lib, asg, sw)): n.setPosition(lights.position() + hou.Vector2(3, -i - 0.5))
    log('built clay switch (sfh_clay_switch, input 1 = clay)')
    return sw

# ---------- Karma ----------
rop = hou.node('/out/sfh_portfolio_rop') or hou.node('/out').createNode('usdrender', 'sfh_portfolio_rop')
rop.parm('loppath').set(karma.path())
if rop.parm('renderer'): rop.parm('renderer').set('BRAY_HdKarma')
# make the ROP BLOCK until husk is done (no background renders, no MPlay), and log what it has
for p in rop.parms():
    lab = (p.parmTemplate().label() + ' ' + p.name()).lower()
    if p.parmTemplate().type() != hou.parmTemplateType.Toggle: continue
    if 'background' in lab or 'mplay' in lab or 'async' in lab:
        p.set(0); log('  rop: %s (%s) -> off' % (p.name(), p.parmTemplate().label()))
    elif 'wait' in lab or 'block' in lab:
        p.set(1); log('  rop: %s (%s) -> on' % (p.name(), p.parmTemplate().label()))
def pick(parm, words):
    if parm is None: return
    for it, lab in zip(parm.menuItems(), parm.menuLabels()):
        if any(w in (it + lab).lower() for w in words): parm.set(it); return it
def karma_render(cam, path, res=None):
    res = res or RES
    os.makedirs(os.path.dirname(path), exist_ok=True)
    setp(karma, 'camera', '/cameras/' + cam)
    setp(karma, 'picture', path)
    setp(karma, 'resolutionx', res[0]); setp(karma, 'resolutiony', res[1])
    setp(karma, 'pathtracedsamples', 32 if QUICK else 256)
    if karma.parm('denoiser'): remember(karma.parm('denoiser')); pick(karma.parm('denoiser'), ('oidn', 'intel'))
    t = time.time()
    try:
        rop.render(frame_range=(1, 1), verbose=False)
        # belt and braces: if the image isn't there yet, husk is running detached -> wait for it (max 30 min)
        while not os.path.exists(path) and time.time() - t < 1800:
            time.sleep(3)
        ok = os.path.exists(path)
        log('  karma %s  (%.0f s)%s' % (os.path.relpath(path, RUN), time.time() - t, '' if ok else '  !! no image after 30 min'))
    except hou.OperationFailed as e:
        log('  !! karma failed %s: %s' % (cam, e))

# ---------- viewport ----------
sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
vp = sv.curViewport()
old_renderer = sv.currentHydraRenderer() if hasattr(sv, 'currentHydraRenderer') else None
def shading(mode):
    for ds in hou.displaySetType.__dict__.values():
        if isinstance(ds, hou.EnumValue):
            try: vp.settings().displaySet(ds).setShadedMode(mode)
            except Exception: pass
def hide_guides():
    # camera / light guide geometry off, so other cameras don't show up in the captures
    st = vp.settings()
    for fn, arg in (('setShowCameras', False), ('setShowLights', False), ('setDisplayCameras', False), ('setDisplayLights', False)):
        try: getattr(st, fn)(arg)
        except Exception: pass
    try:
        for g in (hou.viewportGuide.CameraMask, hou.viewportGuide.NodeGuides, hou.viewportGuide.NodeHandles):
            st.enableGuide(g, False)
    except Exception: pass
def aim_sweep_cam():
    import math
    c = stage.node('sfh_cam_sweep')
    if c is None:
        c = stage.createNode('camera', 'sfh_cam_sweep'); shot = stage.node('sfh_shot_cam')
        c.setInput(0, shot.inputs()[0]); shot.setInput(0, c); c.parm('primpath').set('/cameras/cam_sweep')
        c.setPosition(shot.position() + hou.Vector2(-2, 0.5))
    sb = NET.node('street_build'); sb.cook()
    g = sb.geometry(); bp = hero.node('building_params').geometry()
    W, H = bp.attribValue('W'), bp.attribValue('building_h')
    road = g.attribValue('far_back') - 3.0 - 6.0
    k = ctl.parm('slope').eval(); gy = lambda x: -k * (x - W * 0.5)
    eye = hou.Vector3(W * 0.5 - 11, gy(W * 0.5 - 11) + 3.2, road); tgt = hou.Vector3(W * 0.5 + 3, gy(W * 0.5) + H * 0.45, 0)
    dv = tgt - eye
    c.parmTuple('t').set(tuple(eye))
    c.parmTuple('r').set((math.degrees(math.atan2(dv[1], math.hypot(dv[0], dv[2]))), math.degrees(math.atan2(-dv[0], -dv[2])), 0))
    c.parm('focalLength').set(22)
def aim_gallery_cam():
    # straight-on architectural framing: camera level (verticals stay vertical), lens shifted up to centre the house,
    # standing on the far kerb, focal length chosen so the whole house + a little of each neighbour fits
    c = stage.node('sfh_cam_gallery')
    if c is None:
        c = stage.createNode('camera', 'sfh_cam_gallery'); shot = stage.node('sfh_shot_cam')
        c.setInput(0, shot.inputs()[0]); shot.setInput(0, c); c.parm('primpath').set('/cameras/cam_gallery')
        c.setPosition(shot.position() + hou.Vector2(-2, 1.5))
    sb = NET.node('street_build'); sb.cook()
    bp = hero.node('building_params').geometry()
    W, H = bp.attribValue('W'), bp.attribValue('building_h')
    Htot = H + (3.2 if bp.attribValue('roof_type') == 1 else 1.4)
    far_back = sb.geometry().attribValue('far_back'); far0 = far_back - 3.0
    k = ctl.parm('slope').eval(); gy = lambda x: -k * (x - W * 0.5)
    # like cam_front: stand behind the houses across the street (upstairs window), clip them away
    eye_z = far_back + 12.0; d = eye_z
    hap = 20.955; vap = hap * GALLERY_RES[1] / GALLERY_RES[0]
    f = min(hap * d / (W + 2.0), vap * d / (Htot + 3.0))
    eye_y = gy(W * 0.5) + 4.0
    c.parmTuple('t').set((W * 0.5, eye_y, eye_z)); c.parmTuple('r').set((0, 0, 0))
    c.parm('focalLength').set(f)
    if c.parm('horizontalAperture'): c.parm('horizontalAperture').set(hap)
    if c.parm('verticalAperture'): c.parm('verticalAperture').set(vap)
    if c.parm('aspectratiox'):                       # the camera node derives the vertical aperture from this ratio
        c.parm('aspectratiox').set(GALLERY_RES[0]); c.parm('aspectratioy').set(GALLERY_RES[1])
    yc = gy(W * 0.5) + Htot * 0.5
    for nm in ('verticalApertureOffset', 'vertApertureOffset'):
        if c.parm(nm): c.parm(nm).set((yc - eye_y) * f / d); break
    c.parmTuple('clippingRange').set((eye_z - (far0 - 3.0), 100000.0))
    log('  gallery cam: W %.1f  H %.1f  f %.1f mm  at %.0f m' % (W, Htot, f, d))
    if c.parm('fStop'): c.parm('fStop').set(11.0)
def gl_capture(cam, path, wire=False):
    if cam == 'cam_sweep': aim_sweep_cam()
    hide_guides()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        sv.setCurrentNode(stage.node('sfh_shot_cam')) if hasattr(sv, 'setCurrentNode') else None
        sv.setHydraRenderer('Houdini GL')
        vp.setCamera('/cameras/' + cam)
        shading(hou.glShadingType.HiddenLineInvisible if wire else hou.glShadingType.Smooth)
        fb = sv.flipbookSettings().stash()
        fb.outputToMPlay(False); fb.frameRange((1, 1))
        base = path[:-4] + '.$F4.png'
        fb.output(base); fb.useResolution(True); fb.resolution(GALLERY_RES if cam == 'cam_gallery' else RES)
        sv.flipbook(vp, fb)
        made = path[:-4] + '.0001.png'
        if os.path.exists(made): os.replace(made, path)
        log('  gl %s' % os.path.relpath(path, RUN))
    except Exception as e:
        log('  !! gl capture failed %s: %s' % (cam, e))

try:
    start = time.time()
    if DO_GL or DO_WIRE:
        for cam in CAMERAS:
            if DO_GL: gl_capture(cam, os.path.join(RUN, 'gl', cam + '.png'))
            if DO_WIRE: gl_capture(cam, os.path.join(RUN, 'wire', cam + '.png'), wire=True)
        shading(hou.glShadingType.Smooth)
    if DO_SWEEPS:
        SWEEPS = [  # (folder, node, parm, values)
            ('seed',      hero, 'seed',           list(range(1, 13))),
            ('palette',   hero, 'palette_choice', list(range(1, 13))),
            ('style',     hero, 'style_choice',   [1, 2, 3]),
            ('roof',      hero, 'roof_choice',    [1, 2, 3]),
            ('brackets',  hero, 'bracket_style',  [1, 2, 3, 4]),
            ('ornament',  hero, 'orn_density',    [0.0, 0.25, 0.5, 0.75, 1.0]),
            ('row_count', ctl,  'row_count',      [1, 3, 5, 7]),
            ('slope',     ctl,  'slope',          [0.0, 0.04, 0.08, 0.12]),
        ]
        for folder, node, parm, values in SWEEPS:
            if node.parm(parm) is None: log('skip sweep %s (no parm)' % folder); continue
            remember(node.parm(parm))
            if node.parm(parm).parmTemplate().type() in (hou.parmTemplateType.Int, hou.parmTemplateType.Menu):
                items = list(node.parm(parm).menuItems()) if node.parm(parm).menuItems() else []
                if items and any(isinstance(v, float) for v in values):     # an int menu: walk its real options instead
                    values = [int(it) for it in items if it.lstrip('-').isdigit()][1:] or values
                seen = []
                for v in values:
                    if int(round(v)) not in seen: seen.append(int(round(v)))
                values = seen
            for i, v in enumerate(values):
                node.parm(parm).deleteAllKeyframes(); node.parm(parm).set(v)
                gl_capture(SWEEP_CAM, os.path.join(RUN, 'sweeps', folder, '%02d.png' % i))
            restore_one = saved[node.parm(parm).path()]
            node.parm(parm).deleteAllKeyframes()
            node.parm(parm).setExpression(restore_one[1], restore_one[2]) if restore_one[0] == 'expr' else node.parm(parm).set(restore_one[1])
    if DO_BUILD:
        steps = [('01_one_house',   {(ctl, 'row_count'): 1, (ctl, 'clouds'): 0}),
                 ('02_palette',     {(hero, 'palette_choice'): 4}),
                 ('03_gable',       {(hero, 'roof_choice'): 2}),
                 ('04_row_of_3',    {(ctl, 'row_count'): 3}),
                 ('05_row_of_5',    {(ctl, 'row_count'): 5}),
                 ('06_hill',        {(ctl, 'slope'): 0.08}),
                 ('07_clouds',      {(ctl, 'clouds'): 1})]
        for name, changes in steps:
            for (node, parm), v in changes.items(): setp(node, parm, v)
            gl_capture(SWEEP_CAM, os.path.join(RUN, 'buildup', name + '.png'))
        restore(); saved.clear()
    if DO_GALLERY:
        setp(ctl, 'row_count', 1); setp(look, 'input', LOOKS.get('sunny', 4))
        setp(ctl, 'editable', 0); setp(ctl, 'clouds', 1); setp(ctl, 'night_sky', 0)   # procedural row of 1 = the hero alone
        for sd in GALLERY_SEEDS:
            setp(hero, 'seed', sd)
            aim_gallery_cam()
            if GALLERY_GL: gl_capture('cam_gallery', os.path.join(RUN, 'gallery_gl', 'seed_%03d.png' % sd))
            if GALLERY_KARMA: karma_render('cam_gallery', os.path.join(RUN, 'gallery', 'seed_%03d.exr' % sd), GALLERY_RES)
        restore(); saved.clear()
    if DO_BEAUTY:
        todo = SHOTS or [(l, c) for l in LOOKS for c in CAMERAS]
        for lname, cam in todo:
            setp(look, 'input', LOOKS[lname])
            setp(ctl, 'clouds', 0 if lname == 'night' else 1)        # the self-lit clouds glow grey at night: clear sky instead
            setp(ctl, 'night_sky', 1 if lname == 'night' else 0)
            karma_render(cam, os.path.join(RUN, 'beauty', lname, cam + '.exr'), SHOT_RES.get(cam))
    if DO_CLAY:
        sw = ensure_clay(); setp(look, 'input', LOOKS.get('sunny', 4)); setp(sw, 'input', 1)
        for cam in CAMERAS: karma_render(cam, os.path.join(RUN, 'clay', cam + '.exr'))
    log('done in %.1f min -> %s' % ((time.time() - start) / 60, RUN))
except Exception:
    log('!! stopped:\n' + traceback.format_exc())
finally:
    restore()
    try:
        shading(hou.glShadingType.Smooth)
        if old_renderer: sv.setHydraRenderer(old_renderer)
    except Exception: pass
    LOG.close()
