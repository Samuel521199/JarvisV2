"""Native wire formats behind one model port, with locally resolved credentials."""
import os
import subprocess
import sys
import time

from sdk.protocol import CoreError, PROJECT, canonical, decode
from control.network import NetworkGate


class NativeModel:
    def __init__(self, config, credential_loader, temp_dir=None):
        self.config = config
        self.credential_loader = credential_loader
        self.temp_dir = temp_dir
        self.network = NetworkGate(temp_dir.parent) if temp_dir else None

    def available(self):
        if self.temp_dir:
            from control.development_profile import read
            profile = read(self.temp_dir.parent)
            if profile: return self.config['id'] in profile['allowed_providers']
        # Do not silently use the old application's local-model process.
        if self.config['adapter'] == 'local': return False
        try: return bool(self.credential_loader(self.config['id'], self.config.get('credential_id')))
        except CoreError: return False

    def generate(self, prompt, checkpoint=lambda: None):
        result = self.complete([{'role': 'user', 'content': prompt}], checkpoint, json_mode=True)
        if result['status'] != 'SUCCEEDED': return result
        try:
            value = decode(result['text'])
            if not isinstance(value, dict): raise ValueError()
        except (CoreError, ValueError): return {'status': 'INVALID', 'code': 'model_json', 'usage': result.get('usage', {})}
        return {**result, 'value': value}

    def complete(self, messages, checkpoint=lambda: None, *, json_mode=False, reference_png=None, reference_pngs=None):
        if self.config['adapter'] == 'local': return {'status': 'REJECTED', 'code': 'local_runtime_not_prepared'}
        if (not isinstance(messages, list) or not 1 <= len(messages) <= 41
            or any(not isinstance(m, dict) or set(m) != {'role', 'content'} or m['role'] not in {'user', 'assistant'} or not isinstance(m['content'], str) for m in messages)):
            raise CoreError('model_context', 'Invalid conversation context')
        if len(canonical(messages).encode()) > self.config.get('max_prompt_bytes', 50000):
            raise CoreError('model_input_limit', 'Conversation exceeds the selected model context budget')
        if self.temp_dir:
            from control.development_profile import read
            if read(self.temp_dir.parent):
                from adapters.development_bridge import complete
                return complete(self.temp_dir.parent, self.config, messages, checkpoint, json_mode=json_mode,
                                reference_png=reference_png, reference_pngs=reference_pngs)
        images = []
        if reference_png is not None or reference_pngs is not None:
            from adapters.models.vision import encode_png,validate_encoded
            if reference_png is not None and reference_pngs is not None:raise CoreError('model_image_invalid','Choose one image envelope')
            raw_images=[reference_png] if reference_png is not None else reference_pngs
            if not isinstance(raw_images,list) or not 1<=len(raw_images)<=2:raise CoreError('model_image_invalid','One or two images required')
            if self.config['adapter'] not in {'vertex','gemini'} or messages[-1]['role']!='user':
                raise CoreError('model_vision_unsupported','Reference images require an explicit Gemini route and user message')
            images = validate_encoded([encode_png(raw) for raw in raw_images])
        if self.network and self.network.read()['blocked']:
            return {'status': 'REJECTED', 'code': 'network_disabled'}
        try: credential = self.credential_loader(self.config['id'], self.config.get('credential_id'))
        except CoreError: return {'status': 'REJECTED', 'code': 'credential_unavailable'}
        environment = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR') if k in os.environ}
        if self.temp_dir:
            self.temp_dir.mkdir(exist_ok=True); environment.update(TEMP=str(self.temp_dir), TMP=str(self.temp_dir))
        checkpoint()
        process = subprocess.Popen([sys.executable, '-I', '-B', str(PROJECT / 'adapters/models/native_transport.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        payload = canonical({'config': self.config, 'credential': credential, 'messages': messages, 'json_mode': json_mode, 'images': images}).encode()
        deadline = time.monotonic() + self.config['timeout_seconds']
        try:
            while True:
                checkpoint()
                if self.network:self.network.require_online()
                if time.monotonic() >= deadline: return {'status': 'UNKNOWN', 'code': 'model_timeout'}
                try:
                    output, _ = process.communicate(payload, timeout=.1)
                    if process.returncode: return {'status': 'UNKNOWN', 'code': 'transport_exit'}
                    result = decode(output)
                    if not isinstance(result, dict) or result.get('status') not in {'SUCCEEDED', 'INVALID', 'REJECTED', 'UNKNOWN'}:
                        return {'status': 'UNKNOWN', 'code': 'transport_reply'}
                    return result
                except subprocess.TimeoutExpired: payload = None
        finally:
            if process.poll() is None: process.kill()
            process.communicate()
