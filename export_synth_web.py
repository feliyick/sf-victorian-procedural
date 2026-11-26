# export_synth_web.py: turn synth_render dataset frames into web assets for the portfolio's label explorer.
#   python export_synth_web.py <dataset_dir> <out_dir> [max_frames | stem,stem,...]
# Per frame: beauty JPG, class preview PNG, instance ids packed into a lossless RGB PNG (id = R*65536 + G*256 + B),
# depth preview JPG, normals PNG, and <frame>.json (camera, annotations without RLE). Writes frames.json (index).
import json, os, sys
import numpy as np
from PIL import Image

CLASSES = {
    0: ('background', (0, 0, 0)), 1: ('wall', (128, 128, 128)), 2: ('window', (0, 200, 230)), 3: ('door', (0, 200, 100)),
    4: ('garage', (230, 220, 0)), 5: ('bay', (255, 0, 128)), 6: ('stairs', (255, 150, 0)), 7: ('porch', (150, 90, 230)),
    8: ('roof', (140, 80, 40)), 9: ('ornament', (255, 255, 255)), 10: ('house_number', (230, 30, 30)),
    11: ('road', (50, 50, 60)), 12: ('sidewalk', (190, 190, 180)), 13: ('vegetation', (40, 140, 40)),
    14: ('street_furniture', (60, 90, 220)), 15: ('distant_building', (200, 170, 130)),
    16: ('doorbell', (255, 60, 200)), 255: ('ignore', (255, 0, 255)),
}


def turbo(x):
    """Small polynomial approximation of the Turbo colour map, x in 0..1."""
    x = np.clip(x, 0, 1)[..., None]
    c = np.array([[0.1357, 4.5974, -42.3277, 130.5887, -150.5666, 58.1375],
                  [0.0914, 2.1856, 4.8052, -14.0195, 4.2109, 2.7747],
                  [0.1067, 12.5925, -60.1097, 109.0745, -88.5066, 26.8183]])
    p = np.stack([x[..., 0] ** i for i in range(6)], -1)
    return (np.clip(p @ c.T, 0, 1) * 255).astype(np.uint8)


def main(ds, out, max_frames=None, only=None):
    os.makedirs(out, exist_ok=True)
    coco = json.load(open(os.path.join(ds, 'annotations.json')))
    cats = {c['id']: c['name'] for c in coco['categories']}
    index = []
    for im in coco['images'][:max_frames]:
        stem = os.path.splitext(os.path.basename(im['file_name']))[0]
        if only and stem not in only:
            continue
        root = os.path.join(ds, os.path.dirname(os.path.dirname(im['file_name'])))      # dataset subfolder
        lab = lambda suffix: os.path.join(root, 'labels', stem + suffix)
        Image.open(os.path.join(ds, im['file_name'])).convert('RGB').save(os.path.join(out, stem + '.jpg'), quality=86)
        Image.open(lab('_class_vis.png')).save(os.path.join(out, stem + '_class.png'), optimize=True)
        ins = np.asarray(Image.open(lab('_instance.png'))).astype(np.uint32)
        rgb = np.stack([(ins // 65536) % 256, (ins // 256) % 256, ins % 256], -1).astype(np.uint8)
        Image.fromarray(rgb).save(os.path.join(out, stem + '_ids.png'), optimize=True)
        if os.path.exists(lab('_depth.png')):
            d = np.asarray(Image.open(lab('_depth.png'))).astype(np.float32) / 256.0
            valid = (d > 0) & (d < 255.9);                                  # 0 and the clipped max (sky) = no depth
            d[~valid] = 0; lo, hi = (np.percentile(d[valid], [2, 98]) if valid.any() else (0, 1))
            vis = turbo(1 - (d - lo) / max(hi - lo, 1e-3)); vis[~valid] = 0
            Image.fromarray(vis).save(os.path.join(out, stem + '_depth.jpg'), quality=86)
        if os.path.exists(lab('_normal.png')):
            Image.open(lab('_normal.png')).save(os.path.join(out, stem + '_normal.png'), optimize=True)
        anns = [a for a in coco['annotations'] if a['image_id'] == im['id']]
        by_id = {a['id']: a for a in anns}
        frame = {
            'id': stem, 'width': im['width'], 'height': im['height'], 'seed': im.get('seed'), 'look': im.get('look'),
            'camera_path': im.get('camera_path'), 'camera': im.get('camera'),
            'objects': {str(a['instance_id']): {
                'class': cats.get(a['category_id'], '?'), 'category_id': a['category_id'], 'annotation_id': a['id'],
                'house': a['instance_id'] // 1000 - 1, 'bbox': a['bbox'], 'area': a['area'],
                'bbox_3d': [round(v, 3) for v in a['bbox_3d']] if a.get('bbox_3d') else None,
                'parent': by_id[a['parent_id']]['instance_id'] if a.get('parent_id') in by_id else None,
            } for a in anns},
        }
        json.dump(frame, open(os.path.join(out, stem + '.json'), 'w'))
        layers = ['beauty', 'class', 'instance'] + [k for k, f in (('depth', '_depth.jpg'), ('normal', '_normal.png'))
                                                    if os.path.exists(os.path.join(out, stem + f))]
        index.append({'id': stem, 'seed': im.get('seed'), 'look': im.get('look'), 'camera': (im.get('camera_path') or '').split('/')[-1],
                      'objects': len(anns), 'layers': layers})
        print(stem, len(anns), 'objects')
    json.dump({'frames': index, 'classes': {str(k): {'name': v[0], 'color': '#%02x%02x%02x' % v[1]} for k, v in CLASSES.items()}},
              open(os.path.join(out, 'frames.json'), 'w'), indent=1)


if __name__ == '__main__':
    arg = sys.argv[3] if len(sys.argv) > 3 else None
    if arg and not arg.isdigit():
        main(sys.argv[1], sys.argv[2], only=arg.split(','))
    else:
        main(sys.argv[1], sys.argv[2], int(arg) if arg else None)
