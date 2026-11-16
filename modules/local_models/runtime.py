"""Metadata-only dependency check; the Host never imports inference libraries."""
from importlib import metadata
from sdk.protocol import PROJECT, read_json


def status(speech=False):
    manifest = read_json(PROJECT / ('modules/local_models/speech-runtime.json' if speech else 'modules/local_models/runtime.json'))
    dependencies = []
    for item in manifest['dependencies']:
        try:
            installed = metadata.version(item['distribution'])
        except metadata.PackageNotFoundError:
            installed = None
        dependencies.append({**item, 'installed': installed, 'ready': installed == item['version']})
    return {'id': manifest['runtime'], 'ready': all(x['ready'] for x in dependencies),
            'dependencies': dependencies, 'installation': manifest.get('install_policy','No automatic dependency installation'),
            'portability': manifest.get('portability','Existing pinned CPU runtime required')}
