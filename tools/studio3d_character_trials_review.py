"""Ask Jarvis to inspect bounded, asset-specific character experiments.

Experiment images are evidence only. Model responses are never executed or
promoted to a shared knowledge base.
"""
import hashlib
import time
import uuid

from control.local_access import install_client
from control.recovery.gate import StopGate
from tools import studio3d_character_trial as api
from tools.studio3d_character_iterate import ASSET, DATA, digest, load, save, sha

TRIALS = {
    'body': ('front', None,
             'body-silhouette-trial-20261027/verified-1.png', '形体正面轮廓'),
    'face': ('front', None, 'face-experiment-20261027/face-narrow-trial.png', '面部眼形'),
    'hair': ('right', None, 'hair-volume-20261027/hair-left.png', '侧面头发'),
}


def run():
    base = DATA / 'artifacts/studio3d-character'
    # First attempt received HTTP 400 for exceeding the two-image API limit;
    # the request was confirmed absent from its chat. Preserve that receipt.
    state_path = ASSET / 'metadata/isolated-trials-review-v2.json'
    if state_path.exists():
        raise RuntimeError('Review already exists; inspect status before any repeat')
    trial = load(ASSET / 'metadata/trial.json')
    if api.get('/api/instance').get('root_digest') != hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():
        raise ValueError('Wrong Jarvis instance')
    install_client(api.ORIGIN, DATA)
    state = {'schema': 'jarvis.character.isolated-trials-review.v1', 'asset_id': trial['asset_id'],
             'status': 'RUNNING', 'max_calls': len(TRIALS), 'calls': {},
             'automatic_promotion': False, 'memory_enabled': False}
    save(state_path, state)
    try:
        for key, (view, before, after, focus) in TRIALS.items():
            StopGate(DATA).require_running()
            if (ASSET / 'metadata/STOP').exists():
                raise RuntimeError('Character STOP requested')
            if sha(ASSET / 'references' / (view + '.png')) != trial['reference_sha256'][view]:
                raise ValueError('Reference changed')
            files = [base / p for p in (before, after) if p]
            row = {'status': 'CREATED', 'files': {str(p): sha(p) for p in files}, 'known_usd': None}
            state['calls'][key] = row
            save(state_path, state)
            ids = [trial['reference_ids'][view]]
            for path in files:
                ids.append(api.upload(path, '人物隔离试验实际渲染 ' + key))
                if sha(path) != row['files'][str(path)]:
                    raise ValueError('Trial image changed during upload')
            chat = api.post('/api/chats', {'project_id': trial['project_id']})['id']
            api.post('/api/chat/update', {'id': chat, 'patch': {'title': '人物隔离试验复核 · ' + focus}})
            prompt = ('用户要求依据参考图继续处理人物，重点是人体曲线、脸和头发。'
                      '第一张为用户参考，其余为已有 FBX 派生的人物实际 Blender 试验渲染。'
                      '请只分析本次重点：' + focus + '。'
                      + ('第二张为试验前，第三张为试验后；' if before else '第二张为试验后；')
                      + '指出可见改善及明显缺陷，包括穿插、边缘、比例和参考差异；注意取景和光照不同可能影响判断。'
                      '建议下一步怎样使用 Blender 手工修正及如何验证，不输出代码、不宣称完成或验收。')
            request = 'character-trial-review-' + uuid.uuid4().hex
            row.update(chat_id=chat, request_id=request, images=ids,
                       signature=digest({'text': prompt, 'images': ids, 'route': trial['route']}), status='SUBMITTING')
            save(state_path, state)
            try:
                row['accepted'] = api.post('/api/chat/send', {'chat_id': chat, 'request_id': request, 'text': prompt,
                    **trial['route'], 'reasoning': 'default', 'skill': 'none', 'memory_enabled': False, 'reference_images': ids})
            except BaseException as exc:
                row.update(status='UNKNOWN', error=str(exc)); save(state_path, state); raise
            row['status'] = 'ACCEPTED'; save(state_path, state)
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                StopGate(DATA).require_running()
                turn = next((t for t in api.get('/api/chats/' + chat)['turns'] if t['id'] == request), None)
                if turn and turn['status'] not in ('READY', 'RUNNING'):
                    row.update(status=turn['status'], reply=turn.get('reply'), error=turn.get('error'))
                    try:
                        usage = [u for u in api.get('/api/usage') if u.get('turn_id') == request]
                        amounts = [(u.get('billing') or {}).get('amount') for u in usage]
                        if usage and all(type(x) in (float, int) for x in amounts):
                            row['known_usd'] = sum(amounts)
                    except Exception:
                        pass
                    save(state_path, state)
                    if row['status'] != 'SUCCEEDED':
                        raise RuntimeError('Review did not succeed: ' + key)
                    print(key + ': SUCCEEDED', flush=True)
                    break
                time.sleep(1)
            else:
                row.update(status='UNKNOWN', error='Observation deadline; do not replay'); save(state_path, state)
                raise TimeoutError('Review outcome unknown: ' + key)
        state['status'] = 'REVIEWED'; save(state_path, state)
    except BaseException as exc:
        state.update(status='INTERRUPTED_OR_FAILED', error=str(exc)); save(state_path, state); raise


if __name__ == '__main__':
    run()
