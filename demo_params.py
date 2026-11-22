# demo_params.py: plays a scripted "live editing" demo on the hero house while you screen-record.
# Each step changes one parameter on the asset (you see the parameter panel AND the viewport update), with a pause.
# Start your recording (Cmd+Shift+5), select victorian_house so its panel is visible, Houdini GL viewport, then run:
#   exec(open('/Users/felicityyick/HoudiniProjects/SanFranciscoHouse/demo_params.py', encoding='utf-8').read())
# Everything is put back at the end. Edit STEPS to taste. Stop early: run  hou.session.demo_stop()
import hou, time
NET = hou.node('/obj/sf_house_geometry'); H = NET.node('victorian_house'); C = NET.node('STREET_CONTROLS')
PAUSE = 1.6        # seconds each state is held
STEPS = []
STEPS += [(H, 'seed', v) for v in (3, 11, 27, 42, 58, 77)]                  # whole new houses
STEPS += [(H, 'style_choice', v) for v in (1, 2, 3)]                         # Italianate / Stick / Queen Anne
STEPS += [(H, 'roof_choice', v) for v in (1, 2, 3)]
STEPS += [(H, 'palette_choice', v) for v in (1, 3, 4, 7, 9, 12)]
STEPS += [(H, 'bracket_style', v) for v in (1, 2, 3, 4)]
STEPS += [(H, 'cornice_layout', v) for v in (1, 2, 3, 4)]
STEPS += [(H, 'bevel', v) for v in (0.0, 0.03, 0.012)]
STEPS += [(C, 'row_count', v) for v in (1, 3, 5, 7)]
STEPS += [(C, 'slope', v) for v in (0.0, 0.06, 0.12, 0.06)]
saved = {}
for n, p, _ in STEPS:
    parm = n.parm(p)
    if parm is not None and parm.path() not in saved:
        try: saved[parm.path()] = ('e', parm.expression(), parm.expressionLanguage())
        except hou.OperationFailed: saved[parm.path()] = ('v', parm.eval(), None)
state = {'i': -1, 't': 0.0}
def restore():
    for path, (k, v, lang) in saved.items():
        q = hou.parm(path); q.deleteAllKeyframes()
        q.setExpression(v, lang) if k == 'e' else q.set(v)
def tick():
    if time.time() - state['t'] < PAUSE: return
    state['i'] += 1; state['t'] = time.time()
    if state['i'] >= len(STEPS):
        hou.ui.removeEventLoopCallback(tick); restore(); print('demo done, settings restored'); return
    n, p, v = STEPS[state['i']]
    parm = n.parm(p)
    if parm is None: return
    parm.deleteAllKeyframes(); parm.set(v)
    hou.ui.setStatusMessage('%s.%s = %s' % (n.name(), p, v))
def demo_stop():
    try: hou.ui.removeEventLoopCallback(tick)
    except Exception: pass
    restore(); print('stopped, settings restored')
hou.session.demo_stop = demo_stop
hou.ui.addEventLoopCallback(tick)
print('demo running: %d steps, ~%d s' % (len(STEPS), len(STEPS) * PAUSE))
