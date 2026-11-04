"""Control the opt-in live Jarvis viewer, bound to the current asset candidate.

Example: python -m tools.studio3d_view_control --asset-root 3DModels/PaK38 --list
Then supply --view JSON containing mode/camera/part/isolate/overlay, etc.
No paid call, geometry edit, image generation, baking or LOD operation.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.request
import uuid

from control.local_access import install_client
from host.studio3d_view_control import validate_view

ROOT = Path(__file__).resolve().parents[1]


def png_reference(raw):
    """Losslessly encode the decoded bounded JPEG for existing PNG-only intake."""
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as source:
        if source.format != 'JPEG' or not (1 <= source.width <= 768 and 1 <= source.height <= 512):
            raise ValueError('Expected bounded JPEG viewport')
        rgb = source.convert('RGB')
        output = io.BytesIO()
        rgb.save(output, format='PNG')
        return output.getvalue(), hashlib.sha256(rgb.tobytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asset-root', type=Path, required=True)
    p.add_argument('--origin', default='http://127.0.0.1:18282')
    p.add_argument('--list', action='store_true')
    p.add_argument('--view', type=Path)
    p.add_argument('--client-id')
    p.add_argument('--id', default=None)
    p.add_argument('--no-capture', action='store_true')
    p.add_argument('--wait', type=int, default=30)
    a = p.parse_args()
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}', a.origin) or not 1 <= a.wait <= 60:
        p.error('Use the existing local workbench and a bounded wait')
    asset = a.asset_root.resolve()
    if not asset.is_relative_to(ROOT / '3DModels'):
        p.error('Registered local model directory required')
    current = json.loads((asset / 'metadata/current-model.json').read_text(encoding='utf-8'))['working_candidate']
    model = (asset / current['model']).resolve()
    if not model.is_relative_to(asset) or hashlib.sha256(model.read_bytes()).hexdigest() != current['model_sha256']:
        p.error('Current model content differs from its binding')
    bound = {'asset_id': current['viewer_job_id'], 'sha256': current['model_sha256']}
    install_client(a.origin, ROOT / 'user-data')
    session = json.load(urllib.request.urlopen(a.origin + '/api/session', timeout=10))

    def call(body):
        request = urllib.request.Request(a.origin + '/api/skill/studio3d-inspection', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': a.origin, 'X-Jarvis-Token': session['token']})
        return json.load(urllib.request.urlopen(request, timeout=10))

    live = call({'action': 'list', **bound})
    if a.list:
        print(json.dumps(live, ensure_ascii=False, indent=2))
        return
    choices = [x for x in live['sessions'] if a.client_id is None or x['client_id'] == a.client_id]
    if len(choices) != 1:
        p.error('Enable Jarvis 检视 in the actual model tab; choose --client-id if more than one is connected')
    if not a.view:
        p.error('--view JSON required; an empty object observes without changing the view')
    view = validate_view(json.loads(a.view.read_text(encoding='utf-8')), choices[0]['objects'])
    ident = a.id or uuid.uuid4().hex
    if not re.fullmatch('[a-f0-9]{32}', ident):
        p.error('Explicit hexadecimal request identity required')
    out = asset / 'metadata/interactive-inspection' / ident
    out.mkdir(parents=True, exist_ok=False)  # a consumed identity never replays
    body = {'action': 'request', 'id': ident, 'client_id': choices[0]['client_id'], **bound, 'view': view, 'capture': not a.no_capture}
    (out / 'request.json').write_text(json.dumps(body, indent=2), encoding='utf-8')
    started = time.monotonic()
    record = {'status': 'UNKNOWN', 'model_calls': 0, 'api_estimate_usd': 0, 'local_compute_cost_usd': None, 'source': bound, 'viewer': current['viewer'], 'role': 'Bounded Jarvis local tool; caller selects view, browser executes controls'}
    try:
        row = call(body)
        while row['status'] in ('QUEUED', 'DISPATCHED') and time.monotonic() - started < a.wait:
            time.sleep(.7)
            row = call({'action': 'status', 'id': ident})
        image = row.get('result', {}).pop('image', None)
        if image:
            raw = base64.b64decode(image.split(',', 1)[1], validate=True)
            (out / 'viewport.jpg').write_bytes(raw)
            row['result']['capture_sha256'] = hashlib.sha256(raw).hexdigest()
            row['result']['capture_file'] = 'viewport.jpg'
            png, pixel_hash = png_reference(raw)
            (out / 'viewport.png').write_bytes(png)
            row['result']['reference_file'] = 'viewport.png'
            row['result']['reference_sha256'] = hashlib.sha256(png).hexdigest()
            row['result']['decoded_rgb_sha256'] = pixel_hash
        record.update(row)
        if row['status'] in ('QUEUED', 'DISPATCHED'):
            record['caller_wait_ended'] = True
            record['note'] = 'No automatic replay; inspect original request status before further work'
    except Exception as error:
        record['error'] = type(error).__name__  # never include credentials
        raise
    finally:
        record['elapsed_seconds'] = time.monotonic() - started
        (out / 'receipt.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'id': ident, 'status': record['status'], 'receipt': str(out / 'receipt.json'), 'mode': record.get('result', {}).get('mode')}, ensure_ascii=False))
    if record['status'] != 'SUCCEEDED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
