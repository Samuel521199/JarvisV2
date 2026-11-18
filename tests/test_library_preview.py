import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from host.core import Core
from host.dialogue import DialogueHost
from modules.dialogue.store import Dialogues
from modules.skills.model_library.preview import preview_request, resolve_preview
from modules.skills.model_library.store import Library


def add_display_asset(root, ident='paper-boat', name='纸船', version='lod2'):
    positions = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
                'buffers': [{'byteLength': len(positions)}], 'bufferViews': [{'buffer': 0, 'byteLength': len(positions)}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'type': 'VEC3',
                               'count': 3, 'min': [0, 0, 0], 'max': [1, 1, 0]}]}
    header = json.dumps(document).encode()
    header += b' ' * (-len(header) % 4)
    chunks = struct.pack('<I4s', len(header), b'JSON') + header + struct.pack('<I4s', len(positions), b'BIN\0') + positions
    source = root / 'fixture.glb'
    source.write_bytes(struct.pack('<4sII', b'glTF', 2, len(chunks) + 12) + chunks)
    with Library(root) as library:
        library.put_asset({'id': ident, 'name': name, 'category': 'general', 'kind': 'model'})
        file_id = library.add_file(ident, source, 'game')
        library.add_variant(ident, version, file_id, version.upper(), 'game')


class LibraryPreview(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        Core.initialize(self.root).close()
        add_display_asset(self.root)

    def test_missing_ambiguous_and_exact(self):
        add_display_asset(self.root, 'paper-boat-blue', '纸船蓝色')
        self.assertTrue(resolve_preview(self.root, '纸船', 'lod2')['assistant_action']['auto_open'])
        ambiguous = resolve_preview(self.root, '船', 'lod2')['assistant_action']
        self.assertFalse(ambiguous['auto_open'])
        self.assertEqual(len(ambiguous['choices']), 2)
        for name, level in [('纸船', 'lod3'), ('帽子', 'lod2')]:
            self.assertEqual(resolve_preview(self.root, name, level)['assistant_action']['choices'], [])

    def test_registered_name_precedes_generic_suffix_and_duplicate_names_are_distinct(self):
        add_display_asset(self.root, 'paper-model', '纸船模型')
        found = resolve_preview(self.root, '纸船模型', 'lod2')['assistant_action']
        self.assertEqual(found['choices'][0]['asset'], 'paper-model')
        add_display_asset(self.root, 'second-boat', '纸船')
        found = resolve_preview(self.root, '纸船', 'lod2')['assistant_action']
        self.assertFalse(found['auto_open'])
        self.assertEqual(len({choice['title'] for choice in found['choices']}), 2)

    def test_command_boundaries(self):
        command = {'text': '请帮我打开纸船的 L O D 二。', 'assistant_mode': True}
        self.assertEqual(preview_request(command), ('纸船', 'lod2'))
        for change in [{'assistant_mode': False}, {'text': '如何打开纸船的 LOD2？'},
                       {'attachments': [{'text': '其他工作'}]}, {'text': '打开纸船的 LOD2，然后导出'}]:
            self.assertIsNone(preview_request({**command, **change}))

    def test_real_queue_without_config_or_provider(self):
        store = Dialogues(self.root)
        self.addCleanup(store.close)
        chat = store.create()
        host = DialogueHost(self.root)
        self.addCleanup(host.close)
        command = {'chat_id': chat, 'request_id': 'offline-preview', 'text': '打开纸船的 LOD2',
                   'assistant_mode': True, 'provider': 'auto', 'model': '', 'reasoning': 'default'}
        with patch.object(host, '_pump'), patch('host.dialogue.NativeModel') as provider:
            self.assertFalse(host.submit(command)['existing'])
            host.run(command['request_id'])
            self.assertTrue(host.submit(command)['existing'])
            provider.assert_not_called()
        turn, = store.read(chat)['turns']
        self.assertEqual((turn['status'], turn['provider']), ('SUCCEEDED', 'local-library'))
        choice, = turn['assistant_action']['choices']
        self.assertEqual((choice['asset'], choice['version']), ('paper-boat', 'lod2'))
        self.assertEqual(store.usage(), [])
