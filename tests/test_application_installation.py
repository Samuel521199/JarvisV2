import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import zipfile

from host.application_installation import install
from modules.release_recovery.application import build,inspect_package
from sdk.protocol import CoreError


class ApplicationInstallation(unittest.TestCase):
    def test_registry_runtime_fixture_is_required_without_allowing_other_evaluation_files(self):
        from modules.release_recovery.application import relative
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'source';source.mkdir()
            files={'VERSION':'0.1.2','apps/workbench/server.py':'# test',
                   'modules/registry_composer/registry.py':'# test registry'}
            for name,text in files.items():
                p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            archive=base/'missing.zip';build(source,list(files),archive,'0.1.2')
            package=base/'missing'
            with zipfile.ZipFile(archive) as z:z.extractall(package)
            with self.assertRaises(CoreError) as caught:inspect_package(package)
            self.assertEqual(caught.exception.code,'application_dependency')
            fixture='evals/text-analyzer.json';p=source/fixture;p.parent.mkdir();p.write_text('{}')
            archive=base/'complete.zip';build(source,[*files,fixture],archive,'0.1.2')
            package=base/'complete'
            with zipfile.ZipFile(archive) as z:z.extractall(package)
            inspect_package(package)
            with self.assertRaises(CoreError):relative('evals/arbitrary.py')

    def test_launcher_preserves_original_and_controller_tamper_blocks_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'source';source.mkdir();(source/'apps/workbench').mkdir(parents=True)
            (source/'VERSION').write_text('0.1.2')
            (source/'apps/workbench/server.py').write_text('# test server')
            (source/'apps/workbench/launch.py').write_text('print("SYNTHETIC_CONTROLLER_EXECUTED")')
            archive=base/'package.zip'
            ident=build(source,['VERSION','apps/workbench/server.py','apps/workbench/launch.py'],archive,'0.1.2')
            package=base/'package'
            with zipfile.ZipFile(archive) as z:z.extractall(package)
            home=base/'installation';root=home/'user-data';(root/'deployment').mkdir(parents=True)
            original=b'@echo original launcher\r\n';(home/'StartJarvis.bat').write_bytes(original)
            (root/'sentinel').write_bytes(b'private data must remain')
            app=Mock();app.state.return_value={'active':{'build':ident}}
            with patch('modules.release_recovery.application.Applications',return_value=app):
                result=install(root,home,package)
            self.assertEqual((Path(result['launcher_backup'])/'StartJarvis.bat').read_bytes(),original)
            self.assertEqual((root/'sentinel').read_bytes(),b'private data must remain')
            command=[sys.executable,'-I','-B',str(home/'JarvisLaunch.py'),'--no-browser']
            good=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stderr);self.assertIn('SYNTHETIC_CONTROLLER_EXECUTED',good.stdout)
            controller=Path(result['controller']);(controller/'apps/workbench/launch.py').write_text('print("MUST_NOT_EXECUTE")')
            bad=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0);self.assertNotIn('MUST_NOT_EXECUTE',bad.stdout)
            self.assertIn('controller code changed',bad.stderr)
            with patch('modules.release_recovery.application.Applications',return_value=app):
                with self.assertRaises(CoreError):install(root,home,package)

    def test_unadopted_and_external_data_roots_cannot_replace_launcher(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'data').mkdir()
            with self.assertRaises(CoreError):install(base/'data',base,base)
