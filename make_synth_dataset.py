# make_synth_dataset.py: render a synthetic dataset through houdini-mcp, QA every frame, merge into one COCO file.
#   python make_synth_dataset.py render [--seeds 22,3,...] [--cams cam_wide,cam_street,cam_robot] [--looks golden,sunny]
#   python make_synth_dataset.py merge            # re-run QA + merge on folders already rendered (no Houdini needed)
# Needs the Houdini listener running for `render`. Run it with houdini-mcp's Python (numpy, Pillow, OpenEXR), e.g.
#   ~/HoudiniProjects/houdini-mcp/.venv/bin/python make_synth_dataset.py render
# Output: render/synth_dataset/<cam>_<look>/ per batch (from synth_render) + annotations.json (frames that passed QA)
# + qa_report.json (every frame, its checks, and why any were rejected).
import argparse, json, os, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'render', 'synth_dataset')
SEED_PARM = '/obj/sf_house_geometry/victorian_house/seed'
SEEDS = [22, 3, 11, 27, 42, 58, 77, 101, 150, 202]
CAMS = ['cam_wide', 'cam_street', 'cam_robot']
LOOKS = ['golden', 'sunny']
DISTANT_BUILDING, IGNORE = 15, 255

# QA thresholds
NEAR_BACKDROP_M = 3.0       # a backdrop building this close is blocking the camera (real neighbours are 5 m+)
NEAR_BACKDROP_FRAC = 0.005  # ... over more than 0.5% of the image
MIN_HOUSE_FRAC = 0.05       # at least 5% of pixels should be house classes (1-10)


def qa_frame(sub_dir, stem, n_annotations):
    """Checks one rendered frame from its label maps. Returns (checks dict, list of failure reasons)."""
    cls = np.asarray(Image.open(os.path.join(sub_dir, 'labels', stem + '_class.png')))
    dep = np.asarray(Image.open(os.path.join(sub_dir, 'labels', stem + '_depth.png'))).astype(np.float32) / 256.0
    seen = cls != IGNORE
    near = (cls == DISTANT_BUILDING) & (dep > 0) & (dep < NEAR_BACKDROP_M)
    house = (cls >= 1) & (cls <= 10)
    checks = {'near_backdrop_frac': round(float(near.sum() / seen.sum()), 4),
              'house_frac': round(float((house & seen).sum() / seen.sum()), 4),
              'annotations': n_annotations}
    fails = []
    if checks['near_backdrop_frac'] > NEAR_BACKDROP_FRAC:
        fails.append('backdrop building within %.0f m of the camera covers %.1f%% of the image'
                     % (NEAR_BACKDROP_M, 100 * checks['near_backdrop_frac']))
    if checks['house_frac'] < MIN_HOUSE_FRAC:
        fails.append('houses cover only %.1f%% of the image' % (100 * checks['house_frac']))
    if n_annotations == 0:
        fails.append('no annotations')
    return checks, fails


def merge(subs, keep_flagged=False):
    merged = {'info': {'description': 'Painted Ladies synthetic street dataset (houdini-mcp)'},
              'categories': None, 'images': [], 'annotations': []}
    report = []
    for sub in subs:
        sub_dir = os.path.join(OUT, sub)
        if not os.path.exists(os.path.join(sub_dir, 'annotations.json')):
            print('skip (not rendered):', sub); continue
        c = json.load(open(os.path.join(sub_dir, 'annotations.json')))
        merged['categories'] = c['categories']
        for im in c['images']:
            anns = [a for a in c['annotations'] if a['image_id'] == im['id']]
            stem = os.path.splitext(os.path.basename(im['file_name']))[0]
            checks, fails = qa_frame(sub_dir, stem, len(anns))
            report.append({'file_name': sub + '/' + im['file_name'], 'checks': checks, 'rejected': fails})
            if fails and not keep_flagged:
                continue
            nid = len(merged['images']) + 1
            amap = {a['id']: len(merged['annotations']) + i + 1 for i, a in enumerate(anns)}
            merged['images'].append(dict(im, id=nid, file_name=sub + '/' + im['file_name'],
                                         depth_file=sub + '/' + im['depth_file'], qa=checks, qa_failures=fails))
            for a in anns:
                merged['annotations'].append(dict(a, id=amap[a['id']], image_id=nid,
                                                  parent_id=amap.get(a['parent_id'], 0) if a.get('parent_id') else 0))
    rejected = [r for r in report if r['rejected']]
    merged['info'].update({'frames_rendered': len(report), 'frames_rejected_by_qa': len(rejected),
                           'qa_thresholds': {'near_backdrop_m': NEAR_BACKDROP_M, 'near_backdrop_frac': NEAR_BACKDROP_FRAC,
                                             'min_house_frac': MIN_HOUSE_FRAC}})
    json.dump(merged, open(os.path.join(OUT, 'annotations.json'), 'w'))
    json.dump(report, open(os.path.join(OUT, 'qa_report.json'), 'w'), indent=1)
    print('merged %d images, %d annotations; %d of %d frames rejected by QA'
          % (len(merged['images']), len(merged['annotations']), len(rejected), len(report)))
    for r in rejected:
        print('  rejected', r['file_name'], '-', '; '.join(r['rejected']))
    return merged


def render(seeds, cams, looks, width=640, samples=16, label_samples=2):
    mcp = os.environ.get('HOUDINI_MCP', os.path.expanduser('~/HoudiniProjects/houdini-mcp'))
    sys.path.insert(0, mcp)
    import server                                       # houdini-mcp's tool functions, called directly
    for cam in cams:
        for look in looks:
            sub = '%s_%s' % (cam, look); t = time.time()
            img, summary = server.synth_render(os.path.join(OUT, sub), '/cameras/' + cam, seeds=seeds, seed_parm=SEED_PARM,
                                               width=width, samples=samples, label_samples=label_samples, look=look, name=sub)
            open(os.path.join(OUT, sub, 'preview.png'), 'wb').write(img.data)
            print(time.strftime('%H:%M'), sub, summary, '%.0f min' % ((time.time() - t) / 60), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['render', 'merge'])
    ap.add_argument('--seeds', default=','.join(map(str, SEEDS)))
    ap.add_argument('--cams', default=','.join(CAMS))
    ap.add_argument('--looks', default=','.join(LOOKS))
    ap.add_argument('--keep-flagged', action='store_true', help='keep QA failures in annotations.json (marked)')
    a = ap.parse_args()
    seeds, cams, looks = [int(s) for s in a.seeds.split(',')], a.cams.split(','), a.looks.split(',')
    os.makedirs(OUT, exist_ok=True)
    if a.mode == 'render':
        render(seeds, cams, looks)
    merge(['%s_%s' % (c, l) for c in cams for l in looks], keep_flagged=a.keep_flagged)
