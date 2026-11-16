"""The one-time admission operator cannot replace arbitrary checker/test bytes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from tools import speech_dependency_policy as policy
from tools import admit_speech_runtime as admission
from tools import check_architecture as guard
from sdk.protocol import PROJECT


class SpeechPolicyExtension(unittest.TestCase):
    def original(self):
        text=(PROJECT/'tools/check_architecture.py').read_text(encoding='utf-8')
        text=text.replace(policy.HELPER,'').replace('    speech = speech_permissions(scan_root,runtime,errors)\n','')
        text=text.replace(' and not (top in speech.get(relative,set()))','')
        candidates=[text.encode(),text.replace('\n','\r\n').encode()]
        return next(raw for raw in candidates if hashlib.sha256(raw).hexdigest()==policy.BASE_SHA)
    def test_only_exact_original_checker_is_transformed(self):
        original=self.original();self.assertEqual(policy.extend(original),(PROJECT/'tools/check_architecture.py').read_bytes())
        with self.assertRaises(ValueError):policy.extend(original+b'\n# changed\n')
        with self.assertRaises(ValueError):policy.extend(policy.extend(original))
    def test_old_tests_and_baseline_are_preserved_byte_for_byte(self):
        test=(PROJECT/'tests'/admission.TEST).read_bytes()
        old={'sdk/application_policy.py':b'TESTS=["old_case.py"]\nTEST_SUPPORT=["support.py"]\n',
             'tools/check_architecture.py':self.original(),'tools/architecture-baseline.json':b'{}',
             'tests/old_case.py':b'# original fixed test\n','tests/support.py':b'# original support\n'}
        result,fingerprint=admission.overlay(old,test)
        for name in ('tools/architecture-baseline.json','tests/old_case.py','tests/support.py'):self.assertEqual(result[name],old[name])
        self.assertIn(b'old_case.py',result['sdk/application_policy.py']);self.assertIn(admission.TEST.encode(),result['sdk/application_policy.py'])
        self.assertEqual(len(fingerprint),64)
        with self.assertRaises(ValueError):admission.overlay(old,test+b'\n')
    def test_unreviewed_policy_never_touches_installation(self):
        with self.assertRaises(ValueError):admission.admit(Path('unused'),expected_controller='0'*64,expected_epoch=0,expected_build='0'*64)
    def test_validation_uses_the_fixed_first_party_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);response=Mock(returncode=0,stdout=json.dumps({'approval':{'receipt':{'report':{'passed':True}}}}).encode(),stderr=b'')
            with patch.object(admission.subprocess,'run',return_value=response) as run:
                self.assertTrue(admission.validate(folder,folder,'0'*64,folder/'validation.log')['passed'])
            command=run.call_args.args[0]
            self.assertNotIn('-c',command);self.assertIn(str(folder/'apps/development/releases.py'),command)


if __name__=='__main__':unittest.main()
