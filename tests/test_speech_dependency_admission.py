"""STT registration is confined to its two exact CPU subprocess files."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from tools import check_architecture as guard


class SpeechDependencyAdmission(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name in ('modules/local_models/runtime.json','modules/local_models/speech-runtime.json',
                     'modules/skills/anatomy/runtime-boundary.json','modules/skills/studio3d/runtime.json'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((guard.ROOT/name).read_bytes())
        self.write('adapters/models/local_speech_worker.py','import numpy\nimport onnxruntime\n')
        self.write('adapters/models/speech_features.py','import numpy\n')
    def write(self,name,text):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    def errors(self):
        stream=StringIO()
        with redirect_stdout(stream):failed=guard.check(self.root,policy_root=guard.ROOT)
        result=json.loads(stream.getvalue())['errors'];self.assertEqual(bool(result),failed);return result
    def test_exact_worker_and_feature_imports_are_accepted(self):self.assertEqual(self.errors(),[])
    def test_host_core_and_other_adapters_do_not_inherit_permissions(self):
        for name in ('host/not_allowed.py','control/not_allowed.py','adapters/models/not_allowed.py'):
            with self.subTest(name=name):
                self.write(name,'import numpy\nimport onnxruntime\n')
                self.assertEqual(sum('Unapproved dependency' in e for e in self.errors()),2)
                (self.root/name).unlink()
    def test_feature_cannot_import_inference_or_tokenizers(self):
        for library in ('onnxruntime','tokenizers'):
            self.write('adapters/models/speech_features.py','import '+library+'\n')
            self.assertTrue(any('Unapproved dependency' in e for e in self.errors()))
    def test_worker_cannot_import_another_optional_package(self):
        self.write('adapters/models/local_speech_worker.py','import tokenizers\n')
        self.assertTrue(any('Unapproved dependency' in e for e in self.errors()))
    def test_missing_declaration_grants_nothing(self):
        (self.root/'modules/local_models/speech-runtime.json').unlink()
        self.assertEqual(sum('Unapproved dependency' in e for e in self.errors()),3)
    def test_modified_paths_dependencies_and_versions_are_denied(self):
        path=self.root/'modules/local_models/speech-runtime.json';original=json.loads(path.read_text())
        for patch in ({'worker':'host/not_allowed.py'},{'support_workers':['adapters/models/another.py']},
                      {'dependencies':original['dependencies']+[{'import':'tokenizers','distribution':'tokenizers','version':'0.22.2'}]},
                      {'runtime':'arbitrary'},{'schema':2},{'schema':True}):
            with self.subTest(patch=patch):
                path.write_text(json.dumps({**original,**patch}),encoding='utf-8')
                self.assertTrue(any('Invalid optional speech-runtime' in e for e in self.errors()))
                self.assertEqual(sum('Unapproved dependency' in e for e in self.errors()),3)
    def test_version_pin_change_in_parent_runtime_is_denied(self):
        path=self.root/'modules/local_models/runtime.json';value=json.loads(path.read_text())
        value['dependencies'][0]['version']='unreviewed';path.write_text(json.dumps(value),encoding='utf-8')
        self.assertTrue(any('Invalid optional speech-runtime' in e for e in self.errors()))
    def test_embedding_and_guarded_vector_fallback_are_still_supported(self):
        self.write('adapters/models/local_embedding_worker.py','import numpy\nimport onnxruntime\nimport tokenizers\n')
        self.write('modules/context_knowledge/vectors.py','try:\n import numpy\nexcept ImportError:\n pass\n')
        self.assertEqual(self.errors(),[])


if __name__=='__main__':unittest.main()
