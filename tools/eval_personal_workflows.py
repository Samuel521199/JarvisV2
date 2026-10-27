"""Opt-in live Jarvis evaluation: five synthetic turns, one explicit model, no fallback."""
import argparse
import datetime
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


CASES = [
    ('english', '英语技能验收 · 文字练习', 'english-coach', [
        ('auto', "开始英语练习：我想读懂机器人英文文档，每次10分钟。请用 'The robot ___ (move/moves) forward.' 出一道题，先不要给答案。"),
        ('english-coach', '我的答案：The robot move forward. 请点评，并给一道同类重试题，先不要给重试答案。'),
        ('english-coach', '结束练习，请给本次学习卡。重试题我还没做。'),
    ]),
    ('journal', '日志技能验收 · 事实与纠正', 'journal-review', [
        ('auto', '整理研发日志：2026年10月26日，今天读英文文档20分钟；模型渲染完成；贴图烘焙失败，尚未修复；明天想花15分钟排查。请给事实、待办和1至3个下一步，不设置提醒。'),
        ('journal-review', '更正：不是贴图烘焙失败，是还没开始烘焙；20分钟应为15分钟。请修订日志并保留其他事实。'),
    ]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:18282')
    parser.add_argument('--provider', default='vertex')
    parser.add_argument('--model', default='gemini-3.8-flash')
    parser.add_argument('--case', choices=['all', 'english', 'journal'], default='all')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', action='store_true', help='Make up to five billed model calls through Jarvis.')
    args = parser.parse_args()
    cases = [case for case in CASES if args.case in {'all', case[0]}]
    calls = sum(len(case[3]) for case in cases)
    if not args.run:
        print(json.dumps({'calls': calls, 'cases': cases, 'execution': 'not_requested'}, ensure_ascii=True))
        return
    if args.base not in {'http://127.0.0.1:18282', 'http://127.0.0.1:18284'}:
        parser.error('Use the local main or dedicated evaluation port.')

    def get(path):
        return json.load(urllib.request.urlopen(args.base + path, timeout=15))

    token = get('/api/session')['token']

    def post(path, value):
        request = urllib.request.Request(args.base + path, data=json.dumps(value).encode(),
            headers={'Origin': args.base, 'Content-Type': 'application/json', 'X-Jarvis-Token': token})
        return json.load(urllib.request.urlopen(request, timeout=20))

    report = {'date': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              'provider': args.provider, 'model': args.model, 'max_calls': calls,
              'memory_enabled': False, 'automatic_fallback': False, 'cases': [],
              'quality_review': 'pending_human_review'}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    save()
    for name, title, expected_skill, prompts in cases:
        chat = post('/api/chats', {})['id']
        post('/api/chat/update', {'id': chat, 'patch': {'title': title}})
        case = {'name': name, 'chat_id': chat, 'url': args.base + '/#chat=' + chat, 'turns': []}
        report['cases'].append(case); save()
        for skill, prompt in prompts:
            ident = 'workflow-eval-' + uuid.uuid4().hex
            receipt = {'id': ident, 'prompt': prompt, 'status': 'submitting'}
            case['turns'].append(receipt); save()
            post('/api/chat/send', {'chat_id': chat, 'request_id': ident, 'text': prompt,
                 'provider': args.provider, 'model': args.model, 'reasoning': 'default',
                 'skill': skill, 'memory_enabled': False, 'assistant_mode': True})
            print(json.dumps({'case': name, 'turn': ident, 'state': 'submitted'}), flush=True)
            deadline = time.monotonic() + 150
            while True:
                detail = get('/api/chats/' + chat)
                turn = next(t for t in detail['turns'] if t['id'] == ident)
                if turn['status'] not in {'READY', 'RUNNING'}: break
                if time.monotonic() >= deadline:
                    post('/api/chat/cancel', {'request_id': ident})
                    receipt.update(status='UNKNOWN', error='evaluation_deadline_cancel_requested')
                    save(); return
                time.sleep(1)
            guidance = json.loads(turn['guidance']) if turn.get('guidance') else {}
            receipt.update(status=turn['status'], error=turn.get('error'), reply=turn.get('reply'),
                           usage=turn.get('usage'), skill=guidance.get('id'),
                           skill_version=guidance.get('version'), action=turn.get('assistant_action'),
                           linked_goal=turn.get('linked_goal'), context_count=turn.get('context_count'),
                           workspace=detail.get('workspace'))
            receipt['flow_passed'] = (turn['status'] == 'SUCCEEDED' and guidance.get('id') == expected_skill
                and (turn.get('assistant_action') or {}).get('kind') == 'chat' and not turn.get('linked_goal'))
            save()
            print(json.dumps({'case': name, 'turn': ident, 'status': turn['status'],
                              'flow_passed': receipt['flow_passed'], 'error': turn.get('error')}), flush=True)
            if not receipt['flow_passed']: return  # No retry or downstream calls after a failed case.
    report['all_flow_checks_passed'] = True
    save()


if __name__ == '__main__': main()
