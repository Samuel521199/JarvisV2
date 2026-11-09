"""Build/recheck a disposable candidate with controller-owned tests; do not adopt."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from host.application_release import tracked_runtime, validator
from host.core import Core
from modules.release_recovery.application import build, inspect_package
from sdk.application_policy import TESTS


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work-root',required=True,type=Path);args=parser.parse_args()
    work=args.work_root.resolve();work.mkdir(parents=True,exist_ok=False)
    data=work/'data';Core.initialize(data).close()
    (data/'deployment').mkdir(exist_ok=True)
    # Explicit source review inventory: the new runtime file is not yet tracked.
    names=sorted(set(tracked_runtime(ROOT)+['control/worker/process.py','modules/task_resource/commitments.py','host/commitments.py','apps/workbench/commitments.js','apps/workbench/commitment-time.js','host/assistant_commitments.py','modules/task_resource/commitment_intent.py','apps/workbench/assistant-commitments.js','control/application_compatibility.py','config/runtime-compatibility.json']))
    archive=work/'candidate.zip'
    ident=build(ROOT,names,archive,(ROOT/'VERSION').read_text().strip())
    package=work/'package';package.mkdir()
    with zipfile.ZipFile(archive) as stream:stream.extractall(package)
    inspect_package(package)
    result=validator(data,reviewed_source=True)(package)
    report={'scope':'disposable development candidate; not staged or adopted in production',
            'build':ident,'runtime_files':len(names),'required_test_patterns':TESTS,
            'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'result':result}
    if result.get('test_log'):
        shutil.copyfile(data/'deployment/validation-logs'/result['test_log'],HERE/'package-tests.log')
    (HERE/'package-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    raise SystemExit(not result['passed'])
