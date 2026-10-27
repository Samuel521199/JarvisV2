"""Declared Blender imports never become general Host/adapter permissions."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import check_architecture as guard


class ArchitectureBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-static-boundary-');self.root=Path(self.temp.name)
        for name in ('modules/local_models/runtime.json','modules/skills/anatomy/runtime-boundary.json','modules/skills/studio3d/runtime.json'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((guard.ROOT/name).read_bytes())
        self.write('adapters/studio3d/learning_worker.py','import bpy\nimport bmesh\nfrom mathutils.bvhtree import BVHTree\n')
        self.write('apps/studio3d/learning_worker.py','from adapters.studio3d.learning_worker import main\n')

    def tearDown(self):self.temp.cleanup()
    def write(self,path,text):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    def check(self):
        stream=StringIO()
        with patch.object(guard,'ROOT',self.root),redirect_stdout(stream):failed=guard.check()
        return failed,json.loads(stream.getvalue())['errors']

    def test_declared_subprocess_imports_are_allowed(self):
        self.assertEqual(self.check(),(False,[]))

    def test_host_other_adapter_and_original_worker_do_not_inherit_new_imports(self):
        for name in ('host/forbidden.py','adapters/other.py','adapters/studio3d/worker.py'):
            with self.subTest(path=name):
                self.write(name,'import bmesh\n');failed,errors=self.check()
                self.assertTrue(failed);self.assertTrue(any('Unapproved dependency' in e and 'bmesh' in e for e in errors))
                (self.root/name).unlink()

    def test_missing_or_widened_declaration_remains_denied(self):
        path=self.root/'modules/skills/studio3d/runtime.json';original=json.loads(path.read_text('utf-8'))
        for changed in ({},{**original['learning'],'worker':'adapters/other.py'},
                        {**original['learning'],'dependencies':['bpy','bmesh','mathutils','requests']}):
            with self.subTest(declaration=changed):
                data={**original,'learning':changed};path.write_text(json.dumps(data),encoding='utf-8')
                failed,errors=self.check();self.assertTrue(failed)
                self.assertTrue(any('Unapproved dependency' in e for e in errors))

    def test_sdk_and_business_domain_boundaries_remain_enforced(self):
        self.write('sdk/forbidden.py','import host.core\n')
        self.write('modules/context_knowledge/forbidden.py','import modules.task_resource.plans\n')
        failed,errors=self.check();self.assertTrue(failed)
        self.assertTrue(any('SDK depends on implementation' in e for e in errors))
        self.assertTrue(any('Cross-domain implementation import' in e for e in errors))
