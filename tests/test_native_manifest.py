"""Stdlib-only release checks for the fixed native capability boundary."""
import ast
import json
from pathlib import Path
import unittest
from sdk.native_programs import verify_program

ROOT=Path(__file__).resolve().parents[1]


class NativeManifest(unittest.TestCase):
    def test_seed_method_sources_ship_without_local_asset_tree_or_development_tools(self):
        from modules.context_knowledge.studio3d_experience import catalog,source_current
        for card in catalog()['methods']:
            self.assertTrue(source_current(card),card['id'])
            for source in card['sources']:
                self.assertFalse(source['path'].startswith(('tools/','3DModels/')))

    def test_installed_native_inventory_is_complete_and_intact(self):
        manifest=json.loads((ROOT/'modules/skills/studio3d/worker-programs.json').read_text())
        expected={p.relative_to(ROOT).as_posix() for directory in ('sdk','adapters/studio3d','modules/skills/studio3d','apps/studio3d') for p in (ROOT/directory).glob('*.py')}
        self.assertEqual(set(manifest['sources']),expected)
        for entry in manifest['entries']:self.assertEqual(verify_program(ROOT,ROOT/entry),entry)

    def test_all_native_apps_install_capabilities_before_consumer_imports(self):
        entries=json.loads((ROOT/'modules/skills/studio3d/worker-programs.json').read_text())['entries']
        for entry in entries:
            tree=ast.parse((ROOT/entry).read_text(encoding='utf-8'))
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='install_runtime']
            self.assertEqual(len(calls),1)
            for n in tree.body:
                if isinstance(n,ast.ImportFrom) and n.module and (n.module.startswith('modules.') or n.module.startswith('adapters.studio3d.') and n.module!='adapters.studio3d.learning_worker'):
                    self.assertLess(calls[0].lineno,n.lineno,entry)
